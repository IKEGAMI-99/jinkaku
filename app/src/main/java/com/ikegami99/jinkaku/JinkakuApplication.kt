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
        // remains hard-disabled. Adreno acceleration uses OpenCL only.
        runCatching { Os.setenv("GGML_DISABLE_VULKAN", "1", true) }

        val vendorLibDirs = listOf("/vendor/lib64", "/system/vendor/lib64")
        val existingLd = System.getenv("LD_LIBRARY_PATH").orEmpty()
        val ldPath = (vendorLibDirs + existingLd.split(':').filter { it.isNotBlank() })
            .distinct()
            .joinToString(":")
        runCatching { Os.setenv("LD_LIBRARY_PATH", ldPath, true) }

        val cache = File(cacheDir, "opencl-kernels").apply { mkdirs() }
        runCatching { Os.setenv("GGML_OPENCL_KERNEL_CACHE_DIR", cache.absolutePath, true) }

        // Qualcomm phones expose the OpenCL implementation in /vendor/lib64.
        // The Khronos ICD loader bundled for linking cannot discover it through
        // Android's normal /etc/OpenCL/vendors path, so create a private ICD
        // directory exactly like a working Termux setup does.
        val adrenoDriver = listOf(
            "/vendor/lib64/libOpenCL_adreno.so",
            "/system/vendor/lib64/libOpenCL_adreno.so"
        ).firstOrNull { runCatching { File(it).exists() }.getOrDefault(false) }
        val openClWrapper = listOf(
            "/vendor/lib64/libOpenCL.so",
            "/system/vendor/lib64/libOpenCL.so"
        ).firstOrNull { runCatching { File(it).exists() }.getOrDefault(false) }

        val driver = adrenoDriver ?: openClWrapper
        val icdDir = File(filesDir, "opencl-icd").apply { mkdirs() }
        var icdFile: File? = null
        if (driver != null) {
            icdFile = File(icdDir, "adreno.icd")
            runCatching { icdFile.writeText("$driver\n") }
            runCatching { Os.setenv("OCL_ICD_VENDORS", icdDir.absolutePath, true) }
            runCatching { Os.setenv("OCL_ICD_FILENAMES", driver, true) }
            runCatching { Os.setenv("OCL_ICD_DISABLE_DYNAMIC_LIBRARY_UNLOADING", "1", true) }
        }

        // If Android exposes Qualcomm's public native library to this app, load
        // the vendor wrapper before libjinkaku_llama.so. This avoids the APK's
        // generic ICD loader shadowing the real Qualcomm implementation.
        var preloaded: String? = null
        val preloadCandidates = listOfNotNull(openClWrapper, adrenoDriver).distinct()
        for (candidate in preloadCandidates) {
            val ok = runCatching {
                System.load(candidate)
                true
            }.getOrElse { false }
            if (ok) {
                preloaded = candidate
                break
            }
        }

        logger = AppLogger(this)
        logger.i("APP", "Application started")
        logger.i(
            "APP",
            "Native backend env VulkanDisabled=${System.getenv("GGML_DISABLE_VULKAN")} " +
                "OpenCLDriver=${driver ?: "not-found"} preload=${preloaded ?: "none"} " +
                "icd=${icdFile?.absolutePath ?: "none"} LD_LIBRARY_PATH=$ldPath cache=${cache.absolutePath}"
        )
    }
}
