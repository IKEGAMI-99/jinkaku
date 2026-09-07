package com.ikegami99.jinkaku.ai

import com.ikegami99.jinkaku.data.JinkakuDatabase
import com.ikegami99.jinkaku.data.MemoryRecord
import kotlin.math.ln
import kotlin.math.sqrt

class HashingEmbeddingEngine(private val dimensions: Int = 256) {
    fun embed(text: String): FloatArray {
        val out = FloatArray(dimensions); val normalized = text.lowercase().trim(); val features = mutableListOf<String>()
        features += Regex("[a-z0-9_+.-]+").findAll(normalized).map { it.value }.toList()
        val compact = normalized.replace(Regex("\\s+"), "")
        if (compact.length == 1) features += compact
        for (i in 0 until (compact.length - 1).coerceAtLeast(0)) features += compact.substring(i, i + 2)
        features.forEach { f -> val h=f.hashCode(); val index=(h and Int.MAX_VALUE)%dimensions; out[index] += if (((h ushr 30) and 1)==0) 1f else -1f }
        var norm=0.0; out.forEach { norm += it*it }; val scale=sqrt(norm).toFloat().takeIf { it>0f } ?: 1f; for(i in out.indices) out[i]/=scale
        return out
    }
    fun cosine(a: FloatArray,b: FloatArray): Float { if(a.size!=b.size) return 0f; var s=0f; for(i in a.indices)s+=a[i]*b[i]; return s }
}

data class ScoredMemory(val memory: MemoryRecord,val score: Double)

class MemoryEngine(private val db: JinkakuDatabase,private val embedding: HashingEmbeddingEngine=HashingEmbeddingEngine()) {
    fun retrieve(query:String,topK:Int=10):List<MemoryRecord>{
        val q=embedding.embed(query); val now=System.currentTimeMillis(); val queryTerms=lexicalFeatures(query)
        val scored=db.activeMemories().map { m ->
            val semantic=embedding.cosine(q,m.embedding).toDouble().coerceIn(-1.0,1.0); val terms=lexicalFeatures(m.content+" "+m.tags)
            val keyword=if(queryTerms.isEmpty())0.0 else queryTerms.intersect(terms).size.toDouble()/queryTerms.size; val importance=m.importance/3.0
            val ageDays=(now-m.createdAt).coerceAtLeast(0L)/86_400_000.0; val recency=1.0/(1.0+ageDays/90.0); val access=ln(1.0+m.accessCount)/5.0
            ScoredMemory(m,semantic*0.50+keyword*0.20+importance*0.15+recency*0.10+access.coerceAtMost(1.0)*0.05)
        }.sortedByDescending{it.score}.take(topK).filter{it.score>0.10}
        db.touchMemories(scored.map{it.memory.id}); return scored.map{it.memory}
    }
    fun addCandidate(content:String,type:String,importance:Int,confidence:Int,origin:String,sourceId:Long?,tags:List<String>):Boolean{
        val clean=content.trim().replace(Regex("\\s+")," "); if(clean.length !in 4..700)return false; val vector=embedding.embed(clean)
        if(db.activeMemories(500).any{embedding.cosine(vector,it.embedding)>0.94f})return false
        db.insertMemory(clean,type,importance.coerceIn(0,3),confidence.coerceIn(0,2),origin,vector,sourceId,tags.joinToString(",")); return true
    }
    private fun lexicalFeatures(text:String):Set<String>{ val s=text.lowercase(); val terms=Regex("[a-z0-9_+.-]{2,}").findAll(s).map{it.value}.toMutableSet(); val c=s.replace(Regex("\\s+"),""); for(i in 0 until (c.length-1).coerceAtLeast(0))terms+=c.substring(i,i+2); return terms }
}
