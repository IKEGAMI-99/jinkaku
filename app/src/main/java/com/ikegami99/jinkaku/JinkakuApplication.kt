package com.ikegami99.jinkaku

import android.app.Application
import com.ikegami99.jinkaku.logging.AppLogger

class JinkakuApplication : Application() {
    lateinit var logger: AppLogger
        private set

    override fun onCreate() {
        super.onCreate()

        // CPU-only runtime. Do not probe, preload, or configure OpenCL/Vulkan.
        // This keeps startup deterministic and avoids the instability seen with
        // mobile GPU backends on the target device.
        logger = AppLogger(this)
        logger.i("APP", "Application started")
        logger.i("APP", "Native backend mode=CPU only")
    }
}
