// PADFINITY build root.
//
// The :engine module is a plain Kotlin/JVM library with no Android dependency, so
// it can be compiled and tested on any machine with a JDK — including CI without
// an Android SDK. :app is the Compose application.
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "padfinity"

include(":engine")
include(":app")
