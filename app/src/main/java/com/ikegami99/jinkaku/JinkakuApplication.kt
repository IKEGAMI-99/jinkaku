package com.ikegami99.jinkaku

import android.app.Application
import com.ikegami99.jinkaku.logging.AppLogger

class JinkakuApplication : Application() {
    lateinit var logger: AppLogger
        private set
    override fun onCreate() {
        super.onCreate()
        logger = AppLogger(this)
        logger.i("APP", "Application started")
    }
}
