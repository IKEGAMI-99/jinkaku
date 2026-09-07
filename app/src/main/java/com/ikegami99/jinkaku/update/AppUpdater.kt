package com.ikegami99.jinkaku.update

import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import androidx.core.content.FileProvider
import com.ikegami99.jinkaku.BuildConfig
import com.ikegami99.jinkaku.logging.AppLogger
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

data class UpdateInfo(val versionName:String,val versionCode:Int,val apkUrl:String)
class AppUpdater(private val context:Context,private val logger:AppLogger){
    suspend fun check():UpdateInfo?=withContext(Dispatchers.IO){runCatching{val release=getJson("https://api.github.com/repos/IKEGAMI-99/jinkaku/releases/latest");val assets=release.getJSONArray("assets");var manifestUrl:String?=null;var apkUrl:String?=null;for(i in 0 until assets.length()){val a=assets.getJSONObject(i);val name=a.getString("name");if(name=="version.json")manifestUrl=a.getString("browser_download_url");if(name.endsWith(".apk"))apkUrl=a.getString("browser_download_url")};if(manifestUrl==null||apkUrl==null)return@runCatching null;val manifest=getJson(manifestUrl);val info=UpdateInfo(manifest.getString("versionName"),manifest.getInt("versionCode"),apkUrl);if(info.versionCode>BuildConfig.VERSION_CODE)info else null}.onFailure{logger.e("UPDATE","Update check failed",it)}.getOrNull()}
    private fun getJson(url:String):JSONObject{val c=(URL(url).openConnection() as HttpURLConnection).apply{connectTimeout=15_000;readTimeout=20_000;setRequestProperty("Accept","application/vnd.github+json");setRequestProperty("User-Agent","Jinkaku/${BuildConfig.VERSION_NAME}")};return c.inputStream.bufferedReader().use{JSONObject(it.readText())}.also{c.disconnect()}}
    fun download(info:UpdateInfo):Long{val dir=File(context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS),"updates").apply{mkdirs()};val file=File(dir,"jinkaku-${info.versionName}.apk").also{if(it.exists())it.delete()};val request=DownloadManager.Request(Uri.parse(info.apkUrl)).setTitle("Jinkaku ${info.versionName}").setDescription("Application update").setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED).setDestinationUri(Uri.fromFile(file));val id=(context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager).enqueue(request);context.getSharedPreferences("update",Context.MODE_PRIVATE).edit().putLong("id",id).putString("path",file.absolutePath).apply();logger.i("UPDATE","APK download queued id=$id");return id}
    fun installDownloaded():Boolean{val path=context.getSharedPreferences("update",Context.MODE_PRIVATE).getString("path",null)?:return false;val file=File(path);if(!file.exists()||file.length()==0L)return false;val uri=FileProvider.getUriForFile(context,"${context.packageName}.files",file);val intent=Intent(Intent.ACTION_VIEW).apply{setDataAndType(uri,"application/vnd.android.package-archive");addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)};context.startActivity(intent);return true}
}
