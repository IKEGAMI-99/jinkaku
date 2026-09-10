from pathlib import Path

P=Path('app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt')

def one(s,a,b,n):
    if a not in s: raise RuntimeError('anchor not found: '+n)
    return s.replace(a,b,1)

def rng(s,a,b,v,n):
    try:i=s.index(a);j=s.index(b,i)
    except ValueError as e: raise RuntimeError('range anchor not found: '+n) from e
    return s[:i]+v+s[j:]

def main():
    s=P.read_text()
    if 'CUSTOM_APPEARANCE_V056' in s: return
    if 'DIAGONAL_GLASS_V054' not in s: raise RuntimeError('v054 required')

    for a,b,n in [
      ('import androidx.compose.foundation.border\n','import androidx.compose.foundation.border\nimport androidx.compose.foundation.gestures.detectDragGestures\nimport androidx.compose.foundation.gestures.detectTapGestures\n','gestures'),
      ('import androidx.compose.runtime.Composable\n','import androidx.compose.runtime.Composable\nimport androidx.compose.runtime.CompositionLocalProvider\n','composition local'),
      ('import androidx.compose.ui.Modifier\n','import androidx.compose.ui.Modifier\nimport androidx.compose.ui.graphics.compositeOver\n','composite'),
      ('import androidx.compose.ui.platform.LocalContext\n','import androidx.compose.ui.input.pointer.pointerInput\nimport androidx.compose.ui.layout.onSizeChanged\nimport androidx.compose.ui.platform.LocalContext\nimport androidx.compose.ui.platform.LocalDensity\n','pointer+density'),
      ('import androidx.compose.ui.unit.dp\n','import androidx.compose.ui.unit.Density\nimport androidx.compose.ui.unit.IntSize\nimport androidx.compose.ui.unit.dp\n','density units'),
      ('import java.util.Locale\n','import java.util.Locale\nimport kotlin.math.PI\nimport kotlin.math.atan2\nimport kotlin.math.cos\nimport kotlin.math.sin\nimport kotlin.math.sqrt\n','math')]:
        s=one(s,a,b,n)
    if 'import androidx.compose.ui.graphics.toArgb\n' not in s:
        s=one(s,'import androidx.compose.ui.graphics.luminance\n','import androidx.compose.ui.graphics.luminance\nimport androidx.compose.ui.graphics.toArgb\n','toArgb')

    scheme='''// CUSTOM_APPEARANCE_V056\nprivate fun readableOn(c: Color)=if(c.luminance()>0.179f) Color.Black else Color.White\nprivate fun opaqueOn(c:Color,b:Color)=if(c.alpha<.999f)c.compositeOver(b) else c\nprivate fun modernColorScheme(dark:Boolean, primary:Color, secondary:Color):androidx.compose.material3.ColorScheme {\n    val base=if(dark) ModernDark else ModernLight\n    val tertiary=Color((primary.red+secondary.red)/2f,(primary.green+secondary.green)/2f,(primary.blue+secondary.blue)/2f,1f)\n    return base.copy(\n        primary=primary,onPrimary=readableOn(primary),primaryContainer=primary,onPrimaryContainer=readableOn(primary),\n        secondary=secondary,onSecondary=readableOn(secondary),secondaryContainer=secondary,onSecondaryContainer=readableOn(secondary),\n        tertiary=tertiary,onTertiary=readableOn(tertiary),tertiaryContainer=tertiary,onTertiaryContainer=readableOn(tertiary),\n        surfaceTint=primary,inversePrimary=primary,onBackground=readableOn(base.background),\n        onSurface=readableOn(base.surface),onSurfaceVariant=readableOn(base.surfaceVariant))\n}\nprivate data class AiIconChoice(val key:String,val label:String,val icon:androidx.compose.ui.graphics.vector.ImageVector)\nprivate val AiIconChoices=listOf(\n    AiIconChoice("Sparkle","Sparkle",Icons.Rounded.AutoAwesome), AiIconChoice("Brain","Brain",Icons.Rounded.Psychology),\n    AiIconChoice("Chat","Chat",Icons.Rounded.ChatBubbleOutline), AiIconChoice("Memory","Memory",Icons.Rounded.Memory))\nprivate fun aiIcon(k:String)=AiIconChoices.firstOrNull{it.key==k}?.icon?:Icons.Rounded.AutoAwesome\n\n'''
    s=rng(s,'private fun modernColorScheme(','private fun modernTypingLabel',scheme,'scheme')

    a='''    var accentColor by remember { mutableStateOf(prefs.getString("accent_color", "Purple") ?: "Purple") }\n'''
    b=a+'''    val oldAccent = ModernAccents.firstOrNull { it.name == accentColor } ?: ModernAccents.first()\n    var primaryArgb by remember { mutableStateOf(prefs.getInt("accent_primary_argb", oldAccent.lightPrimary.toArgb())) }\n    var secondaryArgb by remember { mutableStateOf(prefs.getInt("accent_secondary_argb", oldAccent.lightSecondary.toArgb())) }\n    var aiBubbleIcon by remember { mutableStateOf(prefs.getString("ai_bubble_icon", "Sparkle") ?: "Sparkle") }\n    var fontScale by remember { mutableStateOf(prefs.getFloat("font_scale", 1f).coerceIn(.8f,1.35f)) }\n'''
    s=one(s,a,b,'states')
    a='''    fun changeAccentColor(value: String) {\n        val safe = ModernAccents.firstOrNull { it.name == value }?.name ?: "Purple"\n        accentColor = safe\n        prefs.edit().putString("accent_color", safe).apply()\n    }\n'''
    b=a+'''\n    fun setPrimary(c:Color){ primaryArgb=c.toArgb(); prefs.edit().putInt("accent_primary_argb",primaryArgb).apply() }\n    fun setSecondary(c:Color){ secondaryArgb=c.toArgb(); prefs.edit().putInt("accent_secondary_argb",secondaryArgb).apply() }\n    fun setAiIcon(k:String){ aiBubbleIcon=AiIconChoices.firstOrNull{it.key==k}?.key?:"Sparkle"; prefs.edit().putString("ai_bubble_icon",aiBubbleIcon).apply() }\n    fun setFontScale(v:Float){ fontScale=v.coerceIn(.8f,1.35f); prefs.edit().putFloat("font_scale",fontScale).apply() }\n'''
    s=one(s,a,b,'persistence')

    s=one(s,'    MaterialTheme(\n        colorScheme = modernColorScheme(darkMode, accentColor),\n',
      '    val systemDensity = LocalDensity.current\n    CompositionLocalProvider(LocalDensity provides Density(systemDensity.density, systemDensity.fontScale * fontScale)) {\n    MaterialTheme(\n        colorScheme = modernColorScheme(darkMode, Color(primaryArgb), Color(secondaryArgb)),\n','theme open')
    s=one(s,'    }\n}\n\n@Composable\nprivate fun BrandHeader', '    }\n    }\n}\n\n@Composable\nprivate fun BrandHeader','theme close')

    s=one(s,'                    ModernScreen.CHAT -> ModernChatScreen(vm, Modifier.padding(top = padding.calculateTopPadding()))\n',
      '                    ModernScreen.CHAT -> ModernChatScreen(vm, Modifier.padding(top = padding.calculateTopPadding()), aiBubbleIcon)\n','chat args')
    a='''                        accentColor = accentColor,\n                        onAccentColorChange = ::changeAccentColor,\n                        share = { file, mime ->\n'''
    b='''                        accentColor = accentColor,\n                        onAccentColorChange = ::changeAccentColor,\n                        primaryAccent = Color(primaryArgb), onPrimaryAccentChange = ::setPrimary,\n                        secondaryAccent = Color(secondaryArgb), onSecondaryAccentChange = ::setSecondary,\n                        aiBubbleIcon = aiBubbleIcon, onAiBubbleIconChange = ::setAiIcon,\n                        fontScale = fontScale, onFontScaleChange = ::setFontScale,\n                        share = { file, mime ->\n'''
    s=one(s,a,b,'settings args')

    s=one(s,'                            navigationIconContentColor = Color.White,\n                            titleContentColor = Color.White,\n                            actionIconContentColor = Color.White\n',
      '                            navigationIconContentColor = MaterialTheme.colorScheme.onBackground,\n                            titleContentColor = MaterialTheme.colorScheme.onBackground,\n                            actionIconContentColor = MaterialTheme.colorScheme.onBackground\n','top contrast')
    s=s.replace('contentColor = Color.White\n                                    )\n                                ) {\n                                    Icon(\n                                        Icons.Rounded.AutoAwesome,','contentColor = MaterialTheme.colorScheme.onPrimary\n                                    )\n                                ) {\n                                    Icon(\n                                        Icons.Rounded.AutoAwesome,',1)
    s=s.replace('tint = Color.White\n                                    )\n                                }','tint = MaterialTheme.colorScheme.onPrimary\n                                    )\n                                }',1)

    s=one(s,'private fun ModernChatScreen(vm: JinkakuViewModel, modifier: Modifier = Modifier) {\n',
      'private fun ModernChatScreen(vm: JinkakuViewModel, modifier: Modifier = Modifier, aiIconName:String) {\n','chat signature')
    msg='''            items(ui.messages, key = { it.id }) { message ->\n                val user=message.role==ROLE_USER\n                val bg=if(user) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant.copy(alpha=.78f)\n                val fg=readableOn(opaqueOn(bg,MaterialTheme.colorScheme.background))\n                Column(Modifier.fillMaxWidth()) {\n                    Row(Modifier.fillMaxWidth(),horizontalArrangement=if(user) Arrangement.End else Arrangement.Start,verticalAlignment=Alignment.Bottom) {\n                        if(!user){ AiAvatar(aiIconName); Spacer(Modifier.width(8.dp)) }\n                        Surface(shape=if(user) RoundedCornerShape(24.dp,24.dp,6.dp,24.dp) else RoundedCornerShape(24.dp,24.dp,24.dp,6.dp),\n                            color=bg,contentColor=fg,modifier=Modifier.fillMaxWidth(if(user).88f else .78f)) {\n                            Text(message.content,Modifier.padding(horizontal=16.dp,vertical=13.dp),style=MaterialTheme.typography.bodyLarge,color=fg)\n                        }\n                    }\n                    if(!user && telemetry.phase=="DONE" && telemetry.finalTextHash!=null && telemetry.finalTextHash==message.content.hashCode())\n                        Text("Prefill ${telemetry.prefillLabel()} tok/s  ·  Decode ${telemetry.decodeLabel()} tok/s  ·  ${telemetry.generatedTokens} tok  ·  ${telemetry.backend}",Modifier.padding(start=52.dp,top=5.dp),style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant)\n                }\n            }\n'''
    s=rng(s,'            items(ui.messages, key = { it.id }) { message ->','\n\n            if (showTypingBubble) {',msg,'messages')
    typ='''            if (showTypingBubble) {\n                item {\n                    val bg=MaterialTheme.colorScheme.surfaceVariant.copy(alpha=.78f)\n                    val fg=readableOn(opaqueOn(bg,MaterialTheme.colorScheme.background))\n                    Row(verticalAlignment=Alignment.Bottom){ AiAvatar(aiIconName); Spacer(Modifier.width(8.dp)); Surface(shape=RoundedCornerShape(24.dp,24.dp,24.dp,6.dp),color=bg,contentColor=fg){\n                        Row(Modifier.padding(horizontal=16.dp,vertical=13.dp),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(10.dp)){ StatusDot(true); Text(modernTypingLabel(telemetry.generatedTokens),color=fg) }\n                    }}\n                }\n            }\n'''
    s=rng(s,'            if (showTypingBubble) {','\n        }\n\n        Surface(',typ,'typing')
    av='''@Composable\nprivate fun AiAvatar(name:String){\n    Surface(shape=RoundedCornerShape(999.dp),color=MaterialTheme.colorScheme.secondary,contentColor=MaterialTheme.colorScheme.onSecondary,modifier=Modifier.size(38.dp)){\n        Box(contentAlignment=Alignment.Center){ Icon(aiIcon(name),"AI icon",Modifier.size(22.dp),tint=MaterialTheme.colorScheme.onSecondary) }\n    }\n}\n\n'''
    s=one(s,'@Composable\nprivate fun ModernContextCard(',av+'@Composable\nprivate fun ModernContextCard(','avatar')

    sig='''    darkMode: Boolean,\n    onDarkModeChange: (Boolean) -> Unit,\n    accentColor: String,\n    onAccentColorChange: (String) -> Unit,\n    share: (java.io.File, String) -> Unit\n'''
    newsig='''    darkMode: Boolean, onDarkModeChange: (Boolean) -> Unit,\n    accentColor: String, onAccentColorChange: (String) -> Unit,\n    primaryAccent:Color, onPrimaryAccentChange:(Color)->Unit, secondaryAccent:Color, onSecondaryAccentChange:(Color)->Unit,\n    aiBubbleIcon:String, onAiBubbleIconChange:(String)->Unit, fontScale:Float, onFontScaleChange:(Float)->Unit,\n    share: (java.io.File, String) -> Unit\n'''
    s=one(s,sig,newsig,'settings signature')
    sec='''        item { ModernSectionTitle("2色アクセント", Icons.Rounded.Tune) }\n        item { ModernSettingsCard { Column(verticalArrangement=Arrangement.spacedBy(10.dp)){\n            Text("自由カラー",fontWeight=FontWeight.SemiBold)\n            Text("2色をそれぞれカラーホイールから自由に設定します。",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)\n            DualColorPicker(primaryAccent,secondaryAccent,onPrimaryAccentChange,onSecondaryAccentChange)\n        } } }\n        item { ModernSectionTitle("チャット表示", Icons.Rounded.ChatBubbleOutline) }\n        item { ModernSettingsCard { Column(verticalArrangement=Arrangement.spacedBy(12.dp)){\n            Text("AIアイコン",fontWeight=FontWeight.SemiBold)\n            AiIconChoices.chunked(2).forEach{r->Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)){r.forEach{c->FilterChip(aiBubbleIcon==c.key,{onAiBubbleIconChange(c.key)},{Text(c.label)},leadingIcon={Icon(c.icon,null,Modifier.size(18.dp))},modifier=Modifier.weight(1f))}}}\n            HorizontalDivider(); Text("文字サイズ",fontWeight=FontWeight.SemiBold)\n            listOf(listOf("小" to .88f,"標準" to 1f),listOf("大" to 1.16f,"特大" to 1.28f)).forEach{r->Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)){r.forEach{(l,v)->FilterChip(kotlin.math.abs(fontScale-v)<.01f,{onFontScaleChange(v)},{Text("$l ${(v*100).toInt()}%")},modifier=Modifier.weight(1f))}}}\n        } } }\n\n'''
    s=rng(s,'        item { ModernSectionTitle("アクセントカラー", Icons.Rounded.Tune) }','        item { ModernSectionTitle("Persona", Icons.Rounded.Psychology) }',sec,'settings section')

    helpers=r'''private fun hsv(c:Color)=FloatArray(3).also{android.graphics.Color.colorToHSV(c.toArgb(),it)}
private fun hex(c:Color)=String.format(Locale.US,"#%06X",c.toArgb() and 0xFFFFFF)
@Composable private fun DualColorPicker(a:Color,b:Color,onA:(Color)->Unit,onB:(Color)->Unit){
    var edit by remember{mutableStateOf(0)}; val c=if(edit==1)a else b
    if(edit>0) AlertDialog(onDismissRequest={edit=0},title={Text("カラー$edit")},text={ColorWheel(c,if(edit==1)onA else onB)},confirmButton={TextButton({edit=0}){Text("完了")}})
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)){listOf(1 to a,2 to b).forEach{(i,x)->OutlinedButton({edit=i},Modifier.weight(1f)){Surface(shape=RoundedCornerShape(999.dp),color=x,modifier=Modifier.size(24.dp)){};Spacer(Modifier.width(7.dp));Text("カラー$i  ${hex(x)}")}}}
}
@Composable private fun ColorWheel(c:Color,onChange:(Color)->Unit){
    var sz by remember{mutableStateOf(IntSize.Zero)}; val h=remember(c.toArgb()){hsv(c)}
    fun pick(p:Offset){if(sz.width<1)return;val cx=sz.width/2f;val cy=sz.height/2f;val dx=p.x-cx;val dy=p.y-cy;val r=minOf(cx,cy);val d=sqrt(dx*dx+dy*dy);if(d>r)return;val hu=((atan2(dy,dx)*180/PI+360)%360).toFloat();onChange(Color(android.graphics.Color.HSVToColor(floatArrayOf(hu,(d/r).coerceIn(0f,1f),h[2].coerceAtLeast(.05f)))))}
    Column(Modifier.fillMaxWidth(),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.spacedBy(8.dp)){
        Canvas(Modifier.size(220.dp).onSizeChanged{sz=it}.pointerInput(c.toArgb(),sz){detectTapGestures{pick(it)}}.pointerInput(c.toArgb(),sz){detectDragGestures(onDragStart={pick(it)},onDrag={ch,_->pick(ch.position)})}){
            drawCircle(Brush.sweepGradient(listOf(Color.Red,Color.Yellow,Color.Green,Color.Cyan,Color.Blue,Color.Magenta,Color.Red)))
            drawCircle(Brush.radialGradient(listOf(Color.White,Color.Transparent)))
            val an=h[0].toDouble()*PI/180;val r=size.minDimension/2;val m=Offset(size.width/2+cos(an).toFloat()*h[1]*r,size.height/2+sin(an).toFloat()*h[1]*r);drawCircle(readableOn(c),9.dp.toPx(),m,style=androidx.compose.ui.graphics.drawscope.Stroke(2.dp.toPx()))
        }
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){Text("明るさ");Spacer(Modifier.width(8.dp));Slider(h[2],{v->onChange(Color(android.graphics.Color.HSVToColor(floatArrayOf(h[0],h[1],v))))},Modifier.weight(1f))}
        Surface(shape=RoundedCornerShape(12.dp),color=c,contentColor=readableOn(c)){Text(hex(c),Modifier.padding(horizontal=16.dp,vertical=8.dp))}
    }
}

'''
    s=one(s,'@Composable\nprivate fun ModernSectionTitle(',helpers+'@Composable\nprivate fun ModernSectionTitle(','wheel helpers')
    P.write_text('// CUSTOM_APPEARANCE_V056\n'+s)

if __name__=='__main__': main()
