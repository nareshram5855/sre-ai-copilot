#!/usr/bin/env bash
# Deploy Kafka to Minikube and create SRE Copilot topics.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
TOPIC_INCIDENTS="${KAFKA_INCIDENT_TOPIC:-sre.incidents.triage}"
TOPIC_ANOMALIES="${KAFKA_ANOMALY_TOPIC:-sre.observability.anomalies}"

echo "==> Ensuring Minikube is running..."
if ! minikube status >/dev/null 2>&1; then
  echo "    Starting minikube (this may take a minute)..."
  minikube start --cpus=4 --memory=8192 || minikube start
fi

echo "==> Deploying Kafka (namespace: kafka)"
kubectl apply -f "$ROOT/infrastructure/k8s/kafka/kafka.yaml"

echo "==> Waiting for Kafka rollout..."
kubectl rollout status deployment/kafka -n kafka --timeout=180s

echo "==> Creating topics..."
kubectl exec -n kafka deploy/kafka -- bash -c "
  /opt/bitnami/kafka/bin/kafka-topics.sh --create --if-not-exists \
    --bootstrap-server localhost:9092 \
    --topic ${TOPIC_INCIDENTS} --partitions 1 --replication-factor 1
  /opt/bitnami/kafka/bin/kafka-topics.sh --create --if-not-exists \
    --bootstrap-server localhost:9092 \
    --topic ${TOPIC_ANOMALIES} --partitions 1 --replication-factor 1
  /opt/bitnami/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092
"

echo ""
echo "==> Kafka ready in Minikube!"
echo ""
echo "  Port-forward (run in a separate terminal for host backend):"
echo "    make kafka-port-forward"
echo ""
echo "  Then set in .env:"
echo "    KAFKA_ENABLED=true"
echo "    KAFKA_BOOTSTRAP_SERVERS=localhost:9092"
echo ""
