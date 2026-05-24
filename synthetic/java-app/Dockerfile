# Stage 1: compile
FROM eclipse-temurin:17-jdk-jammy AS build
WORKDIR /app
COPY LogGenerator.java .
RUN javac -XDignore.symbol.file LogGenerator.java

# Stage 2: runtime with OTel agent
FROM eclipse-temurin:17-jre-jammy
WORKDIR /app

# Download OTel Java auto-instrumentation agent
ADD https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v2.9.0/opentelemetry-javaagent.jar /app/otel-agent.jar

COPY --from=build /app/*.class .
EXPOSE 8080

ENV JAVA_TOOL_OPTIONS="-javaagent:/app/otel-agent.jar"
ENV OTEL_TRACES_EXPORTER=otlp
ENV OTEL_METRICS_EXPORTER=prometheus
ENV OTEL_LOGS_EXPORTER=none
ENV OTEL_METRIC_EXPORT_INTERVAL=15000
ENV OTEL_EXPORTER_PROMETHEUS_PORT=9464

CMD ["java", \
     "-Xms64m", "-Xmx96m", \
     "-Xlog:gc*:stdout:time", \
     "LogGenerator"]
