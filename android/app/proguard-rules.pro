# ProGuard rules for novel-downloader-android
-keepattributes Signature
-keepattributes *Annotation*

# Hilt
-dontwarn dagger.hilt.**
-keep class dagger.hilt.** { *; }

# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**

# Coroutines
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}

# Room
-keep class * extends androidx.room.RoomDatabase
-keep @androidx.room.Entity class *
-keep @androidx.room.Dao class *
