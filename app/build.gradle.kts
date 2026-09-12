import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

val versionNameProp = providers.gradleProperty("JINKAKU_VERSION_NAME").getOrElse("0.1.0")
val versionCodeProp = providers.gradleProperty("JINKAKU_VERSION_CODE").getOrElse("1").toInt()

android {
    namespace = "com.ikegami99.jinkaku"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.ikegami99.jinkaku"
        minSdk = 33
        targetSdk = 36
        versionCode = versionCodeProp
        versionName = versionNameProp
        // Jinkaku is intentionally arm64-only. LiteRT-LM supplies its own native runtime.
        ndk { abiFilters += listOf("arm64-v8a") }
    }
    signingConfigs {
        create("release") {
            storeFile = rootProject.file("keystore/jinkaku-release.jks")
            storePassword = "jinkaku-local"
            keyAlias = "jinkaku"
            keyPassword = "jinkaku-local"
        }
    }
    buildTypes {
        debug { applicationIdSuffix = ".debug"; versionNameSuffix = "-debug" }
        release { isMinifyEnabled = false; isShrinkResources = false; signingConfig = signingConfigs.getByName("release") }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    buildFeatures { compose = true; buildConfig = true }
    packaging { jniLibs.useLegacyPackaging = true; resources.excludes += setOf("/META-INF/{AL2.0,LGPL2.1}") }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

configurations.configureEach {
    resolutionStrategy.force(
        "org.jetbrains.kotlinx:kotlinx-coroutines-core-jvm:1.11.0",
        "org.jetbrains.kotlinx:kotlinx-coroutines-android:1.11.0",
    )
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2025.12.00"))
    implementation("androidx.activity:activity-compose:1.12.2")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.10.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.10.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core-jvm:1.11.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.11.0")
    implementation("com.google.ai.edge.litertlm:litertlm-android:0.17.0-alpha1")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
