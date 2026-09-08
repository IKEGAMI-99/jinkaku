package com.ikegami99.jinkaku

import android.app.Application
import android.system.Os
import com.ikegami99.jinkaku.logging.AppLogger
import java.io.File

class JinkakuApplication : Application() {
    lateinit var logger: AppLogger
        private set

    override fun onCreate() {
        super.onCreate()

        // Vulkan caused VK_ERROR_DEVICE_LOST on the target POCO F7 Ultra, so it
        // stays hard-disabled. OpenCL is intentionally left enabled for the
        // upstream llama.cpp Adreno backend.
        runCatching { Os.setenv("GGML_DISABLE_VULKAN", "1", true) }

        val cache = File(cacheDir, "opencl-kernels").apply { mkdirs() }
        runCatching { Os.setenv("GGML_OPENCL_KERNEL_CACHE_DIR", cache.absolutePath, true) }

        // The APK ships the Khronos ICD loader. Point it at Qualcomm's vendor
        // implementation when the file is visible to the app linker namespace.
        val driver = listOf(
            "/vendor/lib64/libOpenCL_adreno.so",
            "/vendor/lib64/libOpenCL.so",
            "/system/vendor/lib64/libOpenCL.so"
        ).firstOrNull { runCatching { File(it).exists() }.getOrDefault(false) }
        if (driver != null) {
            runCatching { Os.setenv("OCL_ICD_FILENAMES", driver, true) }
        }

        logger = AppLogger(this)
        logger.i("APP", "Application started")
        logger.i(
            "APP",
            "Native backend env VulkanDisabled=${System.getenv("GGML_DISABLE_VULKAN")} OpenCLDriver=${driver ?: "auto-discovery"} cache=${cache.absolutePath}"
        )
    }
}
