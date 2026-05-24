FROM amazoncorretto:17-alpine
WORKDIR /app
COPY OomApp.java .
RUN javac OomApp.java
# -Xmx64m caps heap at 64MB — OOM guaranteed when K8s limit is 96Mi
# Disable cgroup awareness so JVM ignores the K8s memory limit.
# -Xmx200m asks for 200MB but cgroup limit is 96Mi → kernel OOMKills at 96Mi (exit 137).
CMD ["java", "-XX:-UseContainerSupport", "-Xmx200m", "OomApp"]
