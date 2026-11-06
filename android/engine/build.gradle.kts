// Pure Kotlin/JVM — no Android plugin, no Android dependencies.
//
// This is enforced structurally: the engine compiles with plain `kotlinc`, which
// is how its 135 checks were executed in an environment with no Android SDK.
plugins {
    alias(libs.plugins.kotlin.jvm)
}

kotlin {
    jvmToolchain(17)
}

// The engine's tests are a self-contained harness (no JUnit) so the module needs
// no repository access to be verified. `gradle :engine:verifyEngine` runs them.
tasks.register<JavaExec>("verifyEngine") {
    group = "verification"
    description = "Runs the dependency-free engine test harness."
    mainClass.set("dev.padfinity.engine.EngineTestsKt")
    val testClasses = sourceSets["test"].output
    val mainClasses = sourceSets["main"].output
    classpath = files(mainClasses, testClasses) + sourceSets["test"].runtimeClasspath
    dependsOn("testClasses")
}
