#!/usr/bin/env sh
set -e
if [ ! -f "settings.gradle" ]; then
    echo "Please run this script from the root of the project"
    exit 1
fi
if [ ! -d "gradle/wrapper" ]; then
    echo "Downloading Gradle Wrapper"
    wget https://services.gradle.org/distributions/gradle-7.2-bin.zip -P /tmp
    unzip -q /tmp/gradle-7.2-bin.zip -d /tmp
    mkdir -p gradle/wrapper
    mv /tmp/gradle-7.2/bin/gradle /tmp/gradle-7.2/bin/gradlew
    mv /tmp/gradle-7.2/lib .
    mv /tmp/gradle-7.2/wrapper/gradle-wrapper.jar gradle/wrapper
    mv /tmp/gradle-7.2/wrapper/gradle-wrapper.properties gradle/wrapper
    rm -rf /tmp/gradle-7.2-bin.zip /tmp/gradle-7.2
    chmod +x gradlew
fi
./gradle/wrapper/gradle-wrapper.jar "$@"
