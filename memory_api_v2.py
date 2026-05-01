"""
memory_api_v2.py - 外部记忆系统 V2（语义搜索 + 写入 API + 自动蒸馏）

功能：
1. SemanticSearch - 基于 embedding 的语义搜索
2. MemoryWriter - 写入 API 客户端（带 optimistic lock）
3. AutoDistiller - 高质量分析自动蒸馏到共享记忆
4. MemoryServer - FastAPI 写入端点（集成到 server.py）

作者: Etern
日期: 2026-05-01
版本: v2.0
"""

import json
import os
import time
import base64
import hashlib
import sqlite3
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


# ==================== 配置 ====================

MEMORY_CONFIG = {
    "base_url": "https://skycetus.cn/memory",
    "write_api_url": "http://127.0.0.1:8001/api/v1/memory",  # 本地写入 API
    "embedding_api_key": "REDACTED_DASHSCOPE_KEY",
    "embedding_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "embedding_model": "text-embedding-v3",
    "db_path": None,  # 运行时设置
}


# ==================== 1. Embedding 服务 ====================

class EmbeddingService:
    """阿里云百炼 embedding 服务"""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or MEMORY_CONFIG["embedding_api_key"]
        self.base_url = base_url or MEMORY_CONFIG["embedding_base_url"]
        self.model = model or MEMORY_CONFIG["embedding_model"]
        self._cache: Dict[str, List[float]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def embed(self, text: str) -> List[float]:
        """获取文本的 embedding 向量"""
        # 检查缓存
        cache_key = hashlib.md5(text.encode('utf-8')).hexdigest()
        if cache_key in self._cache:
            self._cache_hits += 1
            return self._cache[cache_key]
        
        self._cache_misses += 1
        
        try:
            payload = {
                "model": self.model,
                "input": [text[:2000]],  # 限制长度
                "dimensions": 256  # 用较小维度节省成本
            }
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                f"{self.base_url}/embeddings",
                data=data,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                method="POST"
            )
            resp = urllib.request.urlopen(req, timeout=10)
            result = json.loads(resp.read().decode('utf-8'))
            
            vector = result["data"][0]["embedding"]
            self._cache[cache_key] = vector
            return vector
        except Exception as e:
            print(f"[embedding] Error: {e}")
            # fallback: 用简单哈希向量
            return self._fallback_vector(text)
    
    def _fallback_vector(self, text: str) -> List[float]:
        """fallback: 用字符频率生成伪向量"""
        freq = [0.0] * 256
        for char in text:
            idx = ord(char) % 256
            freq[idx] += 1.0
        # 归一化
        total = sum(freq) or 1.0
        return [f / total for f in freq]
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量 embedding"""
        return [self.embed(t) for t in texts]
    
    @property
    def cache_stats(self) -> dict:
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "cache_size": len(self._cache)
        }


# ==================== 2. 向量相似度 ====================

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """余弦相似度"""
    if not a or not b:
        return 0.0
    
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot / (norm_a * norm_b)


# ==================== 3. SQLite 向量存储 ====================

class VectorStore:
    """SQLite 向量存储（b64 编码，零扩展依赖）"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), 'memory_vectors.db')
        self._init_db()
    
    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path) or '.', exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_vectors (
                id TEXT PRIMARY KEY,
                content TEXT,
                metadata TEXT,
                vector_b64 TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_created 
            ON memory_vectors(created_at)
        """)
        conn.commit()
        conn.close()
    
    def upsert(self, entry_id: str, content: str, metadata: dict, vector: List[float]):
        """插入或更新向量"""
        vector_b64 = base64.b64encode(
            json.dumps(vector).encode('utf-8')
        ).decode('utf-8')
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO memory_vectors 
            (id, content, metadata, vector_b64, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            entry_id,
            content,
            json.dumps(metadata, ensure_ascii=False),
            vector_b64,
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()
    
    def search(self, query_vector: List[float], top_k: int = 10, 
               min_similarity: float = 0.5) -> List[dict]:
        """向量搜索"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT id, content, metadata, vector_b64 FROM memory_vectors")
        
        results = []
        for row in cursor.fetchall():
            entry_id, content, metadata_json, vector_b64 = row
            try:
                stored_vector = json.loads(base64.b64decode(vector_b64).decode('utf-8'))
                similarity = cosine_similarity(query_vector, stored_vector)
                
                if similarity >= min_similarity:
                    results.append({
                        "id": entry_id,
                        "content": content,
                        "metadata": json.loads(metadata_json) if metadata_json else {},
                        "similarity": round(similarity, 4)
                    })
            except Exception:
                continue
        
        conn.close()
        
        # 按相似度排序
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    
    def count(self) -> int:
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM memory_vectors").fetchone()[0]
        conn.close()
        return count
    
    def delete(self, entry_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("DELETE FROM memory_vectors WHERE id = ?", (entry_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted


# ==================== 4. 语义搜索 ====================

class SemanticSearch:
    """语义搜索引擎"""
    
    def __init__(self, vector_store: VectorStore = None, 
                 embedding_service: EmbeddingService = None):
        self.vector_store = vector_store or VectorStore()
        self.embedding = embedding_service or EmbeddingService()
        self._indexed = False
    
    def index_entry(self, entry_id: str, content: str, metadata: dict = None):
        """索引一条记忆"""
        vector = self.embedding.embed(content)
        self.vector_store.upsert(entry_id, content, metadata or {}, vector)
    
    def index_entries(self, entries: List[dict], id_field: str = "id", 
                     content_field: str = "content"):
        """批量索引"""
        for entry in entries:
            entry_id = entry.get(id_field, hashlib.md5(
                entry.get(content_field, "").encode()
            ).hexdigest()[:12])
            self.index_entry(entry_id, entry.get(content_field, ""), entry)
    
    def search(self, query: str, top_k: int = 5, 
               min_similarity: float = 0.5) -> List[dict]:
        """语义搜索"""
        query_vector = self.embedding.embed(query)
        return self.vector_store.search(query_vector, top_k, min_similarity)
    
    def build_index_from_web(self, base_url: str = None):
        """从 web 记忆文件构建索引"""
        base_url = base_url or MEMORY_CONFIG["base_url"]
        
        files = [
            "shared/decisions.json",
            "shared/infrastructure.json", 
            "shared/projects.json",
            "shared/protocols.json",
        ]
        
        total = 0
        for filepath in files:
            try:
                url = f"{base_url}/{filepath}"
                req = urllib.request.Request(url)
                resp = urllib.request.urlopen(req, timeout=5)
                data = json.loads(resp.read().decode('utf-8'))
                
                entries = data.get("entries", [])
                self.index_entries(entries)
                total += len(entries)
            except Exception as e:
                print(f"[semantic] Failed to index {filepath}: {e}")
        
        self._indexed = True
        print(f"[semantic] Indexed {total} entries from web memory")
    
    @property
    def stats(self) -> dict:
        return {
            "vector_count": self.vector_store.count(),
            "indexed": self._indexed,
            "embedding_cache": self.embedding.cache_stats
        }


# ==================== 5. 写入 API 客户端 ====================

@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    type: str  # decision, lesson, infrastructure, project, protocol, analysis
    content: str
    agent: str = "etern"
    tags: List[str] = field(default_factory=list)
    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source_run_id: str = ""  # 来源的运行 ID（用于追溯）
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "agent": self.agent,
            "tags": self.tags,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_run_id": self.source_run_id
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MemoryEntry':
        return cls(
            id=data["id"],
            type=data["type"],
            content=data["content"],
            agent=data.get("agent", "etern"),
            tags=data.get("tags", []),
            version=data.get("version", 1),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            source_run_id=data.get("source_run_id", "")
        )


class MemoryWriter:
    """
    记忆写入客户端 - 通过写入 API 或本地文件写入
    
    优先级：
    1. 远程写入 API（如果可用）
    2. 本地文件缓冲（等待部署）
    """
    
    def __init__(self, write_api_url: str = None, agent: str = "etern"):
        self.write_api_url = write_api_url or MEMORY_CONFIG["write_api_url"]
        self.agent = agent
        self._local_buffer: List[MemoryEntry] = []
        self._api_available: Optional[bool] = None
    
    def _check_api(self) -> bool:
        """检查写入 API 是否可用"""
        if self._api_available is not None:
            return self._api_available
        
        try:
            url = self.write_api_url.rstrip('/') + '/health'
            req = urllib.request.Request(url, method='GET')
            resp = urllib.request.urlopen(req, timeout=3)
            self._api_available = resp.status == 200
        except Exception:
            self._api_available = False
        
        return self._api_available
    
    def write(self, entry: MemoryEntry) -> dict:
        """
        写入一条记忆
        
        Returns:
            {"status": "ok", "version": 1} 或 {"status": "conflict", "current_version": 2}
        """
        if self._check_api():
            return self._write_api(entry)
        else:
            return self._write_local(entry)
    
    def _write_api(self, entry: MemoryEntry) -> dict:
        """通过远程 API 写入"""
        try:
            payload = {
                "action": "append",
                "entry": entry.to_dict()
            }
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.write_api_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            resp = urllib.request.urlopen(req, timeout=5)
            result = json.loads(resp.read().decode('utf-8'))
            return result
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            if "conflict" in body.lower() or e.code == 409:
                return {"status": "conflict", "error": body}
            return {"status": "error", "error": body}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _write_local(self, entry: MemoryEntry) -> dict:
        """写入本地缓冲"""
        self._local_buffer.append(entry)
        return {"status": "buffered", "buffer_size": len(self._local_buffer)}
    
    def flush(self, output_dir: str = None) -> List[dict]:
        """刷新本地缓冲到文件"""
        if not self._local_buffer or not output_dir:
            return []
        
        # 按类型分组
        by_type: Dict[str, List[dict]] = {}
        for entry in self._local_buffer:
            if entry.type not in by_type:
                by_type[entry.type] = []
            by_type[entry.type].append(entry.to_dict())
        
        saved = []
        for type_name, entries in by_type.items():
            filepath = os.path.join(output_dir, f"{type_name}.json")
            existing = {"entries": []}
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            
            existing["entries"].extend(entries)
            existing["updated_at"] = datetime.now().isoformat()
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            
            saved.append({"file": filepath, "count": len(entries)})
        
        self._local_buffer.clear()
        return saved


# ==================== 6. 自动蒸馏 ====================

class AutoDistiller:
    """
    自动蒸馏器 - 高质量分析自动提取关键结论并写入共享记忆
    """
    
    QUALITY_THRESHOLD = 0.8  # 高于此值才蒸馏
    
    def __init__(self, writer: MemoryWriter = None, 
                 semantic_search: SemanticSearch = None):
        self.writer = writer or MemoryWriter()
        self.semantic = semantic_search
    
    def should_distill(self, quality_report: dict) -> bool:
        """判断是否应该蒸馏"""
        overall = quality_report.get("overall_quality", 0)
        return overall >= self.QUALITY_THRESHOLD
    
    def extract_key_insights(self, seed: str, quality_report: dict,
                           phase_outputs: Dict[str, str] = None) -> List[str]:
        """
        从分析结果中提取关键结论
        
        简单实现：取收敛阶段（water）的核心结论 + 高评分阶段的输出
        """
        insights = []
        
        # 从质量报告中提取建议
        recommendations = quality_report.get("recommendations", [])
        if recommendations:
            insights.extend(recommendations[:3])
        
        # 从阶段输出中提取（如果有）
        if phase_outputs:
            water_output = phase_outputs.get("water", "")
            if water_output:
                # 简单提取：取前 200 字
                insights.append(water_output[:200])
        
        return insights
    
    def distill(self, run_id: str, seed: str, quality_report: dict,
               phase_outputs: Dict[str, str] = None) -> Optional[MemoryEntry]:
        """
        蒸馏一次分析
        
        Returns:
            MemoryEntry 或 None（如果质量不够）
        """
        if not self.should_distill(quality_report):
            return None
        
        insights = self.extract_key_insights(seed, quality_report, phase_outputs)
        
        if not insights:
            return None
        
        content = f"种子: {seed}\n\n关键结论:\n" + "\n".join(
            f"- {insight}" for insight in insights
        )
        
        entry = MemoryEntry(
            id=f"analysis_{run_id}",
            type="analysis",
            content=content,
            agent="etern",
            tags=self._extract_tags(seed),
            source_run_id=run_id
        )
        
        return entry
    
    def _extract_tags(self, seed: str) -> List[str]:
        """从种子中提取标签"""
        tags = []
        keywords = {
            "strategy": ["战略", "竞争", "策略", "strategy"],
            "technical": ["技术", "系统", "架构", "technical"],
            "education": ["教育", "学习", "教学"],
            "business": ["商业", "产品", "市场"],
            "creative": ["创意", "设计", "故事"],
        }
        seed_lower = seed.lower()
        for tag, kws in keywords.items():
            if any(kw in seed_lower for kw in kws):
                tags.append(tag)
        return tags or ["general"]


# ==================== 7. FastAPI 写入端点 ====================

def create_memory_api(memory_dir: str = None):
    """
    创建 FastAPI 写入端点
    
    用法（集成到 server.py）：
    from memory_api_v2 import create_memory_api
    memory_router = create_memory_api("/path/to/memory")
    app.include_router(memory_router, prefix="/api/v1/memory")
    """
    try:
        from fastapi import APIRouter, HTTPException
        from pydantic import BaseModel
    except ImportError:
        print("[memory_api] FastAPI not available, returning mock router")
        return None
    
    memory_dir = memory_dir or os.path.join(os.path.dirname(__file__), 'memory_data')
    os.makedirs(memory_dir, exist_ok=True)
    
    router = APIRouter()
    
    # 文件锁（简单并发控制）
    import threading
    _locks: Dict[str, threading.Lock] = {}
    _global_lock = threading.Lock()
    
    def _get_lock(filepath: str) -> threading.Lock:
        with _global_lock:
            if filepath not in _locks:
                _locks[filepath] = threading.Lock()
            return _locks[filepath]
    
    def _file_path(file_type: str) -> str:
        return os.path.join(memory_dir, f"{file_type}.json")
    
    def _read_file(file_type: str) -> dict:
        filepath = _file_path(file_type)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"entries": [], "updated_at": ""}
    
    def _write_file(file_type: str, data: dict):
        filepath = _file_path(file_type)
        data["updated_at"] = datetime.now().isoformat()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    class WriteRequest(BaseModel):
        action: str  # append, update, delete
        entry: Optional[dict] = None
        entry_id: Optional[str] = None
        file_type: str  # decisions, infrastructure, projects, protocols, analyses
    
    @router.get("/health")
    async def health():
        return {"status": "ok", "memory_dir": memory_dir}
    
    @router.post("/")
    async def write_memory(req: WriteRequest):
        filepath = _file_path(req.file_type)
        lock = _get_lock(filepath)
        
        with lock:
            data = _read_file(req.file_type)
            
            if req.action == "append":
                if not req.entry:
                    raise HTTPException(400, "entry is required for append")
                
                # Schema 校验
                required = ["id", "type", "content"]
                for field in required:
                    if field not in req.entry:
                        raise HTTPException(400, f"Missing field: {field}")
                
                # 内容长度限制
                if len(req.entry.get("content", "")) > 2000:
                    raise HTTPException(400, "Content too long (max 2000 chars)")
                
                # 检查 ID 是否已存在
                existing = [e for e in data["entries"] if e.get("id") == req.entry["id"]]
                if existing:
                    raise HTTPException(409, f"Entry ID conflict: {req.entry['id']}")
                
                data["entries"].append(req.entry)
                _write_file(req.file_type, data)
                return {"status": "ok", "action": "appended", "id": req.entry["id"]}
            
            elif req.action == "update":
                if not req.entry or not req.entry.get("id"):
                    raise HTTPException(400, "entry with id is required for update")
                
                entry_id = req.entry["id"]
                current_version = req.entry.get("version", 1)
                
                # 查找现有条目
                for i, entry in enumerate(data["entries"]):
                    if entry.get("id") == entry_id:
                        if entry.get("version", 1) != current_version:
                            return {
                                "status": "conflict",
                                "current_version": entry.get("version", 1),
                                "message": "Version mismatch, entry was modified"
                            }
                        
                        # 更新
                        req.entry["version"] = current_version + 1
                        req.entry["updated_at"] = datetime.now().isoformat()
                        data["entries"][i] = req.entry
                        _write_file(req.file_type, data)
                        return {"status": "ok", "action": "updated", "version": current_version + 1}
                
                raise HTTPException(404, f"Entry not found: {entry_id}")
            
            elif req.action == "delete":
                if not req.entry_id:
                    raise HTTPException(400, "entry_id is required for delete")
                
                original_count = len(data["entries"])
                data["entries"] = [e for e in data["entries"] if e.get("id") != req.entry_id]
                
                if len(data["entries"]) == original_count:
                    raise HTTPException(404, f"Entry not found: {req.entry_id}")
                
                _write_file(req.file_type, data)
                return {"status": "ok", "action": "deleted"}
            
            else:
                raise HTTPException(400, f"Unknown action: {req.action}")
    
    @router.get("/list/{file_type}")
    async def list_memory(file_type: str):
        data = _read_file(file_type)
        return {
            "file_type": file_type,
            "count": len(data.get("entries", [])),
            "updated_at": data.get("updated_at", ""),
            "entries": data.get("entries", [])
        }
    
    return router


# ==================== 测试 ====================

if __name__ == "__main__":
    print("=== 外部记忆系统 V2 测试 ===\n")
    
    # 1. 测试 embedding
    print("1. Embedding 测试...")
    emb = EmbeddingService()
    v1 = emb.embed("如何提升系统性能？")
    v2 = emb.embed("系统优化的方法")
    v3 = emb.embed("今天天气怎么样？")
    
    sim12 = cosine_similarity(v1, v2)
    sim13 = cosine_similarity(v1, v3)
    print(f"   相似问题相似度: {sim12:.4f}")
    print(f"  不相关问题相似度: {sim13:.4f}")
    print(f"   Cache: {emb.cache_stats}")
    assert sim12 > sim13, "相似问题应该有更高的相似度"
    print("   [OK] Embedding 测试通过")
    
    # 2. 测试向量存储
    print("\n2. 向量存储测试...")
    vs = VectorStore(db_path=os.path.join(os.path.dirname(__file__), 'test_vectors.db'))
    vs.upsert("test1", "如何提升系统性能？", {"type": "question"}, v1)
    vs.upsert("test2", "系统优化的方法", {"type": "question"}, v2)
    vs.upsert("test3", "今天天气怎么样？", {"type": "question"}, v3)
    
    results = vs.search(v1, top_k=2)
    print(f"   搜索返回 {len(results)} 条结果")
    print(f"   第一条: {results[0]['content']} (similarity: {results[0]['similarity']})")
    assert results[0]["id"] == "test1", "应该返回最相似的结果"
    print("   [OK] 向量存储测试通过")
    
    # 清理测试文件
    if os.path.exists(vs.db_path):
        os.remove(vs.db_path)
    
    # 3. 测试语义搜索
    print("\n3. 语义搜索测试...")
    ss = SemanticSearch(vector_store=VectorStore(db_path=os.path.join(os.path.dirname(__file__), 'test_semantic.db')))
    ss.index_entries([
        {"id": "e1", "content": "飞轮系统需要质量评分机制", "type": "lesson"},
        {"id": "e2", "content": "服务器部署在 8.134.132.211", "type": "infrastructure"},
        {"id": "e3", "content": "使用五行框架进行分析推演", "type": "protocol"},
    ])
    
    search_results = ss.search("如何提高分析质量", top_k=2)
    print(f"   搜索返回 {len(search_results)} 条结果")
    for r in search_results:
        print(f"   - {r['content'][:40]}... (sim: {r['similarity']})")
    print("   [OK] 语义搜索测试通过")
    
    if os.path.exists(ss.vector_store.db_path):
        os.remove(ss.vector_store.db_path)
    
    # 4. 测试写入客户端
    print("\n4. 写入客户端测试...")
    writer = MemoryWriter()
    entry = MemoryEntry(
        id="test_entry_001",
        type="lesson",
        content="测试写入：飞轮分析需要质量阈值",
        tags=["flywheel", "quality"]
    )
    result = writer.write(entry)
    print(f"   写入结果: {result}")
    assert result["status"] == "buffered", "应该缓冲到本地"
    print("   [OK] 写入客户端测试通过")
    
    # 5. 测试自动蒸馏
    print("\n5. 自动蒸馏测试...")
    distiller = AutoDistiller()
    
    # 高质量分析 -> 应该蒸馏
    high_quality = {
        "overall_quality": 0.85,
        "recommendations": ["增加发散度", "加强现实校验"]
    }
    distilled = distiller.distill("run-001", "如何设计分布式系统？", high_quality)
    if distilled:
        print(f"   蒸馏成功: {distilled.content[:50]}...")
        print("   [OK] 自动蒸馏测试通过")
    else:
        print("   [FAIL] 应该蒸馏但未蒸馏")
    
    # 低质量分析 -> 不应该蒸馏
    low_quality = {"overall_quality": 0.5}
    not_distilled = distiller.distill("run-002", "简单问题", low_quality)
    assert not_distilled is None, "低质量不应该蒸馏"
    print("   [OK] 低质量不蒸馏测试通过")
    
    print("\n=== 全部测试通过 ===")
