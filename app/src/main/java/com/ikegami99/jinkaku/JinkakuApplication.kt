package com.ikegami99.jinkaku

import android.app.Application
import android.system.Os
import com.ikegami99.jinkaku.logging.AppLogger

class JinkakuApplication : Application() {
    lateinit var logger: AppLogger
        private set

    override fun onCreate() {
        super.onCreate()

        // llmedge/ggml may register GPU backends even when model options request CPU.
        // Disable them at the process level before any native inference class is touched.
        runCatching { Os.setenv("GGML_DISABLE_VULKAN", "1", true) }
        runCatching { Os.setenv("GGML_DISABLE_OPENCL", "1", true) }

        logger = AppLogger(this)
        logger.i("APP", "Application started")
        logger.i(
            "APP",
            "Native GPU backends disabled env Vulkan=${System.getenv("GGML_DISABLE_VULKAN")} OpenCL=${System.getenv("GGML_DISABLE_OPENCL")}"
        )
    }
}
