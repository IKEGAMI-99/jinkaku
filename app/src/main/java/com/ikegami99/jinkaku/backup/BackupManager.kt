package com.ikegami99.jinkaku.backup

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import com.ikegami99.jinkaku.BuildConfig
import com.ikegami99.jinkaku.data.JinkakuDatabase
import com.ikegami99.jinkaku.logging.AppLogger
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream

class BackupManager(private val context:Context,private val db:JinkakuDatabase,private val logger:AppLogger){
    fun createBackup():File{db.checkpoint();val dir=File(context.cacheDir,"backups").apply{mkdirs()};val out=File(dir,"Jinkaku_backup_${System.currentTimeMillis()}.zip");ZipOutputStream(FileOutputStream(out)).use{zip->zip.putNextEntry(ZipEntry("manifest.json"));zip.write(JSONObject().put("version",1).put("appVersion",BuildConfig.VERSION_NAME).toString(2).toByteArray());zip.closeEntry();val dbFile=db.dbFile();zip.putNextEntry(ZipEntry("jinkaku.db"));dbFile.inputStream().use{it.copyTo(zip)};zip.closeEntry()};require(out.length()>0){"Backup is empty"};logger.i("BACKUP","Backup created bytes=${out.length()}");return out}
    fun restoreFrom(zipFile:File):Boolean=runCatching{val temp=File(context.cacheDir,"restore-${System.currentTimeMillis()}.db");ZipFile(zipFile).use{zip->val entry=zip.getEntry("jinkaku.db")?:error("jinkaku.db missing");zip.getInputStream(entry).use{input->temp.outputStream().use{input.copyTo(it)}}};val check=SQLiteDatabase.openDatabase(temp.absolutePath,null,SQLiteDatabase.OPEN_READONLY);val ok=check.rawQuery("PRAGMA integrity_check",null).use{it.moveToFirst()&&it.getString(0).equals("ok",true)};check.close();require(ok){"SQLite integrity_check failed"};db.close();temp.copyTo(context.getDatabasePath("jinkaku.db"),overwrite=true);temp.delete();logger.i("BACKUP","Restore completed; process restart required");true}.onFailure{logger.e("BACKUP","Restore failed",it)}.getOrDefault(false)
}
