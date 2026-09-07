package com.ikegami99.jinkaku.ai

import android.content.Context
import com.ikegami99.jinkaku.logging.AppLogger
import io.aatricks.llmedge.LLMEdge
import io.aatricks.llmedge.model.ModelSpec
import io.aatricks.llmedge.text.TextModelOptions
import io.aatricks.llmedge.text.TextStreamEvent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import java.io.File

sealed interface GenerationEvent { data object Thinking:GenerationEvent; data class Text(val value:String):GenerationEvent; data class Completed(val finalText:String,val elapsedMs:Long):GenerationEvent }

class E4BEngine(private val context:Context,private val scope:CoroutineScope,private val logger:AppLogger):AutoCloseable{
    private var edge:LLMEdge?=null
    private fun runtime():LLMEdge=edge?:LLMEdge.create(context,scope).also{edge=it}
    fun generate(model:File,prompt:String,systemPrompt:String,contextSize:Long):Flow<GenerationEvent> = flow {
        require(model.exists()&&model.length()>0L){"E4B GGUF model is not installed"}; logger.i("E4B","Generation start model=${model.name} size=${model.length()} ctx=$contextSize")
        val started=System.currentTimeMillis(); val filter=ThinkingFilter(); var final=""; var thinkingSent=false
        runtime().text.stream(prompt=prompt,model=ModelSpec.localFile(model),systemPrompt=systemPrompt,options=TextModelOptions(contextSize=contextSize,temperature=1.0f,useMmap=true,useMlock=false,useFlashAttention=true,useVulkan=false)).collect{event->
            when(event){
                is TextStreamEvent.Started->{emit(GenerationEvent.Thinking);thinkingSent=true}
                is TextStreamEvent.Chunk->{val visible=filter.accept(event.value);if(visible.isNotEmpty()){if(!thinkingSent){emit(GenerationEvent.Thinking);thinkingSent=true};final+=visible;emit(GenerationEvent.Text(visible))}}
                is TextStreamEvent.Completed->{val tail=filter.finish();if(tail.isNotEmpty()){final+=tail;emit(GenerationEvent.Text(tail))}}
            }
        }
        val elapsed=System.currentTimeMillis()-started; logger.i("E4B","Generation complete elapsedMs=$elapsed chars=${final.length}"); emit(GenerationEvent.Completed(final.trim(),elapsed))
    }
    fun unload(){runCatching{edge?.close()}.onFailure{logger.e("E4B","Runtime close failed",it)};edge=null;logger.i("E4B","Runtime unloaded")}
    override fun close()=unload()
}

private class ThinkingFilter{
    private var inThinking=false;private var pending="";private val startMarkers=listOf("<|channel>thought","<|channel>analysis","<think>");private val endMarkers=listOf("<|channel>final","</think>","<channel|>");private val maxMarker=(startMarkers+endMarkers).maxOf{it.length}
    fun accept(chunk:String):String{pending+=chunk;val out=StringBuilder();while(pending.isNotEmpty()){
        if(!inThinking){val start=startMarkers.map{pending.indexOf(it)}.filter{it>=0}.minOrNull();if(start!=null){out.append(pending.substring(0,start));val marker=startMarkers.first{pending.startsWith(it,start)};pending=pending.substring(start+marker.length);inThinking=true;continue};val keep=(maxMarker-1).coerceAtMost(pending.length);val safe=pending.length-keep;if(safe<=0)break;out.append(pending.substring(0,safe));pending=pending.substring(safe)}
        else{val end=endMarkers.map{pending.indexOf(it)}.filter{it>=0}.minOrNull();if(end!=null){val marker=endMarkers.first{pending.startsWith(it,end)};pending=pending.substring(end+marker.length);inThinking=false;continue};if(pending.length>maxMarker)pending=pending.takeLast(maxMarker)else break}
    };return out.toString()}
    fun finish():String{val tail=if(inThinking)"" else pending;pending="";return tail}
}
