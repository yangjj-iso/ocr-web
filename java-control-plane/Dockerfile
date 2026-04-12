FROM docker.m.daocloud.io/library/maven:3.9.9-eclipse-temurin-17 AS builder

WORKDIR /build

COPY java-control-plane/pom.xml ./pom.xml
RUN mvn -q -DskipTests dependency:go-offline

COPY java-control-plane/src ./src
RUN mvn -q -DskipTests package

FROM docker.m.daocloud.io/library/eclipse-temurin:17-jre

WORKDIR /app

COPY --from=builder /build/target/java-control-plane-0.0.1-SNAPSHOT.jar /app/app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
