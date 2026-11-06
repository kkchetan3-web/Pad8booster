# PADFINITY release rules.
# The engine is pure data classes + logic; nothing needs reflection there except
# the desktop codec's enum valueOf() calls, which R8 must not strip.
-keepclassmembers enum dev.padfinity.engine.** {
    public static **[] values();
    public static ** valueOf(java.lang.String);
}
# Shizuku is looked up reflectively; keep the class names we probe for.
-keep class rikka.shizuku.** { *; }
-dontwarn rikka.shizuku.**
