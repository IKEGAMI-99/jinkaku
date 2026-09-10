from pathlib import Path

P = Path('app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt')


def one(s: str, old: str, new: str, label: str) -> str:
    if old not in s:
        raise RuntimeError('anchor not found: ' + label)
    return s.replace(old, new, 1)


def main() -> None:
    s = P.read_text(encoding='utf-8')
    if 'AVATAR_CROP_V058' in s:
        print('AVATAR_CROP_V058 already applied')
        return
    if 'CUSTOM_AI_AVATAR_V057' not in s:
        raise RuntimeError('v057 required')

    old_avatar = '''@Composable
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

    new_avatar = '''// AVATAR_CROP_V058
@Composable
private fun AiAvatar(name:String, customPath:String?){
    val customBitmap=remember(customPath){ customPath?.let{p->runCatching{BitmapFactory.decodeFile(p)?.asImageBitmap()}.getOrNull()} }
    val avatarShape=androidx.compose.foundation.shape.CircleShape
    Box(
        modifier=Modifier
            .size(38.dp)
            .clip(avatarShape)
            .background(MaterialTheme.colorScheme.secondary),
        contentAlignment=Alignment.Center
    ){
        if(customBitmap!=null){
            Image(
                bitmap=customBitmap,
                contentDescription="AI custom icon",
                contentScale=androidx.compose.ui.layout.ContentScale.Crop,
                alignment=Alignment.Center,
                modifier=Modifier.fillMaxSize()
            )
        }else{
            Icon(aiIcon(name),"AI icon",Modifier.size(22.dp),tint=MaterialTheme.colorScheme.onSecondary)
        }
    }
}
'''

    s = one(s, old_avatar, new_avatar, 'avatar renderer')
    s = one(
        s,
        '            Text("選択画像は端末内のJINKAKU専用領域へコピーし、AIバブル横に円形で表示します。",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)\n',
        '            Text("選択画像は中央を正方形にトリミングし、円形マスク内に収めてAIバブル横へ表示します。",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)\n',
        'avatar settings help',
    )

    P.write_text(s, encoding='utf-8')
    print('Applied AVATAR_CROP_V058: hard circular mask + centered crop for custom AI avatar')


if __name__ == '__main__':
    main()
