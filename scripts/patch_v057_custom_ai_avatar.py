from pathlib import Path

P = Path('app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt')


def one(s: str, old: str, new: str, label: str) -> str:
    if old not in s:
        raise RuntimeError('anchor not found: ' + label)
    return s.replace(old, new, 1)


def main() -> None:
    s = P.read_text(encoding='utf-8')
    if 'CUSTOM_AI_AVATAR_V057' in s:
        print('CUSTOM_AI_AVATAR_V057 already applied')
        return
    if 'CUSTOM_APPEARANCE_V056' not in s:
        raise RuntimeError('v056 required')

    s = one(
        s,
        '    var aiBubbleIcon by remember { mutableStateOf(prefs.getString("ai_bubble_icon", "Sparkle") ?: "Sparkle") }\n',
        '    var aiBubbleIcon by remember { mutableStateOf(prefs.getString("ai_bubble_icon", "Sparkle") ?: "Sparkle") }\n'
        '    var customAiAvatarPath by remember { mutableStateOf(prefs.getString("ai_avatar_custom_path", null)) }\n',
        'custom avatar state',
    )

    s = one(
        s,
        '    fun setAiIcon(k:String){ aiBubbleIcon=AiIconChoices.firstOrNull{it.key==k}?.key?:"Sparkle"; prefs.edit().putString("ai_bubble_icon",aiBubbleIcon).apply() }\n',
        '    fun setAiIcon(k:String){ aiBubbleIcon=AiIconChoices.firstOrNull{it.key==k}?.key?:"Sparkle"; prefs.edit().putString("ai_bubble_icon",aiBubbleIcon).apply() }\n'
        '    fun setCustomAiAvatarPath(path:String?){ customAiAvatarPath=path; val e=prefs.edit(); if(path==null)e.remove("ai_avatar_custom_path") else e.putString("ai_avatar_custom_path",path); e.apply() }\n',
        'custom avatar persistence',
    )

    s = one(
        s,
        '                    ModernScreen.CHAT -> ModernChatScreen(vm, Modifier.padding(top = padding.calculateTopPadding()), aiBubbleIcon)\n',
        '                    ModernScreen.CHAT -> ModernChatScreen(vm, Modifier.padding(top = padding.calculateTopPadding()), aiBubbleIcon, customAiAvatarPath)\n',
        'chat custom avatar arg',
    )

    s = one(
        s,
        '                        aiBubbleIcon = aiBubbleIcon, onAiBubbleIconChange = ::setAiIcon,\n'
        '                        fontScale = fontScale, onFontScaleChange = ::setFontScale,\n',
        '                        aiBubbleIcon = aiBubbleIcon, onAiBubbleIconChange = ::setAiIcon,\n'
        '                        customAiAvatarPath = customAiAvatarPath, onCustomAiAvatarPathChange = ::setCustomAiAvatarPath,\n'
        '                        fontScale = fontScale, onFontScaleChange = ::setFontScale,\n',
        'settings custom avatar args',
    )

    s = one(
        s,
        'private fun ModernChatScreen(vm: JinkakuViewModel, modifier: Modifier = Modifier, aiIconName:String) {\n',
        'private fun ModernChatScreen(vm: JinkakuViewModel, modifier: Modifier = Modifier, aiIconName:String, customAiAvatarPath:String?) {\n',
        'chat signature',
    )
    count = s.count('AiAvatar(aiIconName)')
    if count != 2:
        raise RuntimeError(f'expected 2 AiAvatar calls, found {count}')
    s = s.replace('AiAvatar(aiIconName)', 'AiAvatar(aiIconName, customAiAvatarPath)')

    old_avatar = '''@Composable
private fun AiAvatar(name:String){
    Surface(shape=RoundedCornerShape(999.dp),color=MaterialTheme.colorScheme.secondary,contentColor=MaterialTheme.colorScheme.onSecondary,modifier=Modifier.size(38.dp)){
        Box(contentAlignment=Alignment.Center){ Icon(aiIcon(name),"AI icon",Modifier.size(22.dp),tint=MaterialTheme.colorScheme.onSecondary) }
    }
}
'''
    new_avatar = '''// CUSTOM_AI_AVATAR_V057
private fun saveCustomAiAvatar(context:android.content.Context, uri:android.net.Uri):String? = runCatching {
    val resolver=context.contentResolver
    val bounds=android.graphics.BitmapFactory.Options().apply{inJustDecodeBounds=true}
    resolver.openInputStream(uri)?.use{android.graphics.BitmapFactory.decodeStream(it,null,bounds)}
    if(bounds.outWidth<=0 || bounds.outHeight<=0) return@runCatching null
    var sample=1
    while(maxOf(bounds.outWidth,bounds.outHeight)/sample>1024) sample*=2
    val opts=android.graphics.BitmapFactory.Options().apply{inSampleSize=sample;inPreferredConfig=android.graphics.Bitmap.Config.ARGB_8888}
    val decoded=resolver.openInputStream(uri)?.use{android.graphics.BitmapFactory.decodeStream(it,null,opts)} ?: return@runCatching null
    val side=minOf(decoded.width,decoded.height)
    val cropped=android.graphics.Bitmap.createBitmap(decoded,(decoded.width-side)/2,(decoded.height-side)/2,side,side)
    val scaled=if(side>512) android.graphics.Bitmap.createScaledBitmap(cropped,512,512,true) else cropped
    val out=java.io.File(context.filesDir,"ai_avatar_${System.currentTimeMillis()}.png")
    java.io.FileOutputStream(out).use{scaled.compress(android.graphics.Bitmap.CompressFormat.PNG,100,it)}
    if(scaled!==cropped) scaled.recycle()
    if(cropped!==decoded) cropped.recycle()
    if(!decoded.isRecycled) decoded.recycle()
    out.absolutePath
}.getOrNull()

@Composable
private fun AiAvatar(name:String, customPath:String?){
    val customBitmap=remember(customPath){ customPath?.let{p->runCatching{BitmapFactory.decodeFile(p)?.asImageBitmap()}.getOrNull()} }
    Surface(shape=RoundedCornerShape(999.dp),color=MaterialTheme.colorScheme.secondary,contentColor=MaterialTheme.colorScheme.onSecondary,modifier=Modifier.size(38.dp)){
        Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center){
            if(customBitmap!=null) Image(bitmap=customBitmap,contentDescription="AI custom icon",contentScale=androidx.compose.ui.layout.ContentScale.Crop,modifier=Modifier.fillMaxSize().clip(RoundedCornerShape(999.dp)))
            else Icon(aiIcon(name),"AI icon",Modifier.size(22.dp),tint=MaterialTheme.colorScheme.onSecondary)
        }
    }
}
'''
    s = one(s, old_avatar, new_avatar, 'avatar renderer')

    s = one(
        s,
        '    aiBubbleIcon:String, onAiBubbleIconChange:(String)->Unit, fontScale:Float, onFontScaleChange:(Float)->Unit,\n',
        '    aiBubbleIcon:String, onAiBubbleIconChange:(String)->Unit, customAiAvatarPath:String?, onCustomAiAvatarPathChange:(String?)->Unit, fontScale:Float, onFontScaleChange:(Float)->Unit,\n',
        'settings signature',
    )

    s = one(
        s,
        '    var personaDraft by remember { mutableStateOf(vm.currentPersona()) }\n',
        '    var personaDraft by remember { mutableStateOf(vm.currentPersona()) }\n'
        '    val avatarContext=LocalContext.current\n'
        '    val avatarPicker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri-> if(uri!=null){ val old=customAiAvatarPath; val path=saveCustomAiAvatar(avatarContext,uri); if(path!=null){ onCustomAiAvatarPathChange(path); if(old!=null && old!=path) runCatching{java.io.File(old).delete()} } } }\n',
        'settings avatar picker',
    )

    s = one(
        s,
        '            HorizontalDivider(); Text("文字サイズ",fontWeight=FontWeight.SemiBold)\n',
        '            Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(8.dp)){\n'
        '                OutlinedButton({avatarPicker.launch("image/*")},modifier=Modifier.weight(1f)){Icon(Icons.Rounded.FolderOpen,null,Modifier.size(18.dp));Spacer(Modifier.width(6.dp));Text(if(customAiAvatarPath==null) "画像を選択" else "画像を変更")}\n'
        '                if(customAiAvatarPath!=null) OutlinedButton({runCatching{java.io.File(customAiAvatarPath).delete()};onCustomAiAvatarPathChange(null)}){Icon(Icons.Rounded.DeleteOutline,null,Modifier.size(18.dp));Spacer(Modifier.width(5.dp));Text("画像を削除")}\n'
        '            }\n'
        '            Text("選択画像は端末内のJINKAKU専用領域へコピーし、AIバブル横に円形で表示します。",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)\n'
        '            HorizontalDivider(); Text("文字サイズ",fontWeight=FontWeight.SemiBold)\n',
        'settings avatar controls',
    )

    P.write_text(s,encoding='utf-8')
    print('Applied CUSTOM_AI_AVATAR_V057: local custom image picker, internal copy, circular AI avatar and reset')


if __name__ == '__main__':
    main()
