plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
}
android {
    namespace = "com.qwen.tts.studio"
    compileSdk = 36
    ndkVersion = "29.0.13113456"
    defaultConfig {
        minSdk = 33
        ndk { abiFilters += listOf("arm64-v8a") }
        externalNativeBuild {
            cmake {
                targets += "qwen3_tts_jni"
                arguments += listOf("-DANDROID_STL=c++_shared", "-DQWEN3_ANDROID_OPENMP=OFF", "-DQWEN3_ANDROID_VULKAN=OFF", "-DQWEN3_ANDROID_OPENCL=OFF")
            }
        }
    }
    buildTypes { release { isMinifyEnabled = false } }
    externalNativeBuild {
        cmake { path = file("src/main/cpp/CMakeLists.txt"); version = "3.31.6" }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
kotlin {
    compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) }
}
