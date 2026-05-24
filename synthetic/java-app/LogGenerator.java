import com.sun.net.httpserver.HttpServer;
import java.io.*;
import java.net.*;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Synthetic Order Service — generates realistic Java production logs.
 *
 * Failure modes (triggered via HTTP /simulate/<issue>):
 *   oom              — unbounded HashMap growth → OutOfMemoryError
 *   npe              — NullPointerException in order processing
 *   deadlock         — thread starvation / lock contention
 *   connection_pool  — HikariCP pool exhaustion
 *   gc_pressure      — frequent full GC with long pauses
 *   high_latency     — slow downstream service calls
 *   normal           — baseline healthy behaviour
 */
public class LogGenerator {

    static final String SERVICE   = System.getenv().getOrDefault("SERVICE_NAME", "order-service");
    static final String VERSION   = System.getenv().getOrDefault("SERVICE_VERSION", "1.8.3");
    static final String ENV       = System.getenv().getOrDefault("ENVIRONMENT", "production");
    static final int    PORT      = Integer.parseInt(System.getenv().getOrDefault("PORT", "8080"));

    static volatile String mode = "normal";
    static final AtomicLong requestCount  = new AtomicLong();
    static final AtomicLong errorCount    = new AtomicLong();
    static final AtomicLong dbErrorCount  = new AtomicLong();
    static final Map<String, byte[]> leakMap = new ConcurrentHashMap<>();
    static final Random rng = new Random();

    static final String[] THREAD_NAMES = {
        "http-nio-8080-exec-1", "http-nio-8080-exec-2", "http-nio-8080-exec-3",
        "http-nio-8080-exec-4", "scheduling-1", "async-task-executor-1"
    };
    static final String[] CUSTOMERS  = {
        "cust_001@bank.internal","cust_002@bank.internal","cust_003@fintech.io",
        "cust_004@corp.com","svc-account@payments.internal"
    };
    static final String[] DB_HOSTS   = {"postgres-orders:5432","postgres-orders-replica:5432"};
    static final String[] SERVICES   = {"payment-service","inventory-service","notification-service"};

    // ── Timestamp ─────────────────────────────────────────────────────────────

    static String ts() {
        return new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'").format(new Date());
    }

    static String tid() { return String.format("%016x", rng.nextLong()); }
    static String sid() { return String.format("%08x",  rng.nextInt());  }
    static String thread() { return THREAD_NAMES[rng.nextInt(THREAD_NAMES.length)]; }

    // ── JSON structured log emitter (Loki-ready) ──────────────────────────────

    static void emit(String level, String logger, String msg) {
        emit(level, logger, msg, new String[0]);
    }

    static void emit(String level, String logger, String msg, String... kvPairs) {
        StringBuilder sb = new StringBuilder();
        sb.append("{");
        sb.append("\"ts\":\"").append(ts()).append("\",");
        sb.append("\"level\":\"").append(level).append("\",");
        sb.append("\"service\":\"").append(SERVICE).append("\",");
        sb.append("\"env\":\"").append(ENV).append("\",");
        sb.append("\"version\":\"").append(VERSION).append("\",");
        sb.append("\"trace_id\":\"").append(tid()).append("\",");
        sb.append("\"span_id\":\"").append(sid()).append("\",");
        sb.append("\"thread\":\"").append(thread()).append("\",");
        sb.append("\"component\":\"").append(logger).append("\",");
        sb.append("\"msg\":\"").append(msg.replace("\"", "'")).append("\"");
        for (int i = 0; i + 1 < kvPairs.length; i += 2) {
            sb.append(",\"").append(kvPairs[i]).append("\":\"")
              .append(kvPairs[i+1].replace("\"", "'")).append("\"");
        }
        sb.append("}");
        System.out.println(sb);
        System.out.flush();
    }

    // Stack traces emitted as a JSON array field "stacktrace"
    static void emitStack(String level, String logger, String msg, String... lines) {
        StringBuilder stack = new StringBuilder("[");
        for (int i = 0; i < lines.length; i++) {
            if (i > 0) stack.append(",");
            stack.append("\"").append(lines[i].replace("\"","'").replace("\\","\\\\")).append("\"");
        }
        stack.append("]");

        StringBuilder sb = new StringBuilder();
        sb.append("{");
        sb.append("\"ts\":\"").append(ts()).append("\",");
        sb.append("\"level\":\"").append(level).append("\",");
        sb.append("\"service\":\"").append(SERVICE).append("\",");
        sb.append("\"env\":\"").append(ENV).append("\",");
        sb.append("\"version\":\"").append(VERSION).append("\",");
        sb.append("\"trace_id\":\"").append(tid()).append("\",");
        sb.append("\"span_id\":\"").append(sid()).append("\",");
        sb.append("\"thread\":\"").append(thread()).append("\",");
        sb.append("\"component\":\"").append(logger).append("\",");
        sb.append("\"msg\":\"").append(msg.replace("\"","'")).append("\",");
        sb.append("\"stacktrace\":").append(stack);
        sb.append("}");
        System.out.println(sb);
        System.out.flush();
    }

    // ── Scenario generators ───────────────────────────────────────────────────

    static void genNormalOrder() {
        String orderId   = "ORD-" + String.format("%08d", requestCount.incrementAndGet());
        String customer  = CUSTOMERS[rng.nextInt(CUSTOMERS.length)];
        double amount    = 10 + rng.nextDouble() * 990;
        long   latencyMs = (long)(20 + rng.nextGaussian() * 15);
        latencyMs = Math.max(5, latencyMs);

        emit("INFO",  "c.e.order.OrderController",
             String.format("POST /api/orders → 201 CREATED | order=%s customer=%s amount=%.2f latency=%dms",
                           orderId, customer, amount, latencyMs));
        if (rng.nextDouble() < 0.15) {
            emit("DEBUG", "c.e.order.InventoryClient",
                 String.format("Stock check: item_id=%s warehouse=WH-EAST reserved=%d",
                               "ITEM-" + rng.nextInt(9999), rng.nextInt(100)));
        }
    }

    static void genNPE() {
        errorCount.incrementAndGet();
        String orderId = "ORD-" + String.format("%08d", rng.nextInt(99999));
        emitStack("ERROR", "c.e.order.OrderService",
            String.format("Failed to process order %s", orderId),
            "java.lang.NullPointerException: Cannot invoke \"com.example.order.Item.getPrice()\" because \"item\" is null",
            "\tat com.example.order.OrderService.calculateTotal(OrderService.java:87)",
            "\tat com.example.order.OrderService.processOrder(OrderService.java:52)",
            "\tat com.example.order.OrderController.createOrder(OrderController.java:34)",
            "\tat sun.reflect.NativeMethodAccessorImpl.invoke0(Native Method)",
            "\tat org.springframework.web.servlet.FrameworkServlet.service(FrameworkServlet.java:897)",
            "\t... 42 more"
        );
        emit("WARN", "c.e.order.OrderController",
             String.format("POST /api/orders → 500 INTERNAL_SERVER_ERROR | order=%s", orderId));
    }

    static void genOOM() {
        // Grow the leak map
        String key = UUID.randomUUID().toString();
        leakMap.put(key, new byte[1024 * 50]); // 50KB per entry

        int mbUsed = (leakMap.size() * 50) / 1024;
        emit("WARN", "c.e.order.HealthMonitor",
             String.format("Heap pressure: approx %dMB leaked | live_objects=%d", mbUsed, leakMap.size()));

        if (leakMap.size() > 1000) {
            emitStack("ERROR", "c.e.order.OrderService",
                "Critical memory error — order processing aborted",
                "java.lang.OutOfMemoryError: Java heap space",
                "\tat java.util.HashMap.resize(HashMap.java:704)",
                "\tat java.util.HashMap.putVal(HashMap.java:663)",
                "\tat com.example.order.cache.OrderCache.put(OrderCache.java:44)",
                "\tat com.example.order.OrderService.cacheOrder(OrderService.java:121)",
                "\t... 38 more"
            );
            emit("ERROR", "c.e.order.App",
                 "JVM heap exhausted — triggering System.exit(1)");
            System.exit(1);
        }
    }

    static void genConnectionPool() {
        dbErrorCount.incrementAndGet();
        int poolUsed = 18 + rng.nextInt(3);
        long waitMs  = 25000 + rng.nextInt(5000);
        emitStack("ERROR", "com.zaxxer.hikari.pool.HikariPool",
            String.format("HikariPool-1 - Connection is not available, request timed out after %dms", waitMs),
            "java.sql.SQLTransientConnectionException: HikariPool-1 - Connection is not available",
            "\tat com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:213)",
            "\tat com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:163)",
            "\tat com.example.order.repository.OrderRepository.findByCustomer(OrderRepository.java:78)",
            "\tat com.example.order.OrderService.getOrderHistory(OrderService.java:156)",
            "\t... 31 more"
        );
        emit("ERROR", "c.e.order.OrderRepository",
             String.format("DB pool exhausted: %d/20 connections active | queue=87 | host=%s",
                           poolUsed, DB_HOSTS[rng.nextInt(DB_HOSTS.length)]));
    }

    static void genGCPressure() {
        long pauseMs = 500 + rng.nextInt(3500);
        double heapPct = 85 + rng.nextDouble() * 14;
        emit("WARN", "sun.misc.GC",
             String.format("[Full GC (Ergonomics) pause=%dms] heap=%.1f%% after_gc=%.1f%%",
                           pauseMs, heapPct, heapPct - rng.nextDouble() * 5));
        emit("WARN", "c.e.order.HealthMonitor",
             String.format("GC pause exceeded SLA: %dms > 200ms threshold | consecutive_pauses=%d",
                           pauseMs, rng.nextInt(15) + 3));
        if (pauseMs > 2000) {
            emit("ERROR", "c.e.order.HealthMonitor",
                 "Stop-the-world GC pause detected — all threads suspended");
        }
    }

    static void genDeadlock() {
        emitStack("ERROR", "c.e.order.PaymentService",
            "Thread deadlock detected by watchdog",
            "Found 2 deadlocked threads:",
            "\"http-nio-8080-exec-2\" waiting to lock <0x000000078e3a2d10> (com.example.order.PaymentService)",
            "\theld by \"async-task-executor-1\"",
            "\"async-task-executor-1\" waiting to lock <0x000000078e3a1f20> (com.example.order.InventoryService)",
            "\theld by \"http-nio-8080-exec-2\""
        );
        emit("ERROR", "c.e.order.WatchdogThread",
             "Deadlock detected — interrupting affected threads | affected_threads=2 | timeout_seconds=30");
    }

    static void genHighLatency() {
        String svc     = SERVICES[rng.nextInt(SERVICES.length)];
        long latencyMs = 3000 + rng.nextInt(12000);
        emit("WARN", "c.e.order.ServiceClient",
             String.format("Slow downstream call: %s → %dms (SLA=500ms)", svc, latencyMs));
        emit("WARN", "c.e.order.CircuitBreaker",
             String.format("Circuit breaker: %s failure_rate=%.1f%% state=%s",
                           svc, 40 + rng.nextDouble() * 50,
                           rng.nextDouble() < 0.3 ? "OPEN" : "HALF_OPEN"));
        if (latencyMs > 8000) {
            emit("ERROR", "c.e.order.OrderController",
                 String.format("GET /api/orders → 504 Gateway Timeout | upstream=%s waited=%dms", svc, latencyMs));
            errorCount.incrementAndGet();
        }
    }

    // ── Metrics endpoint body ─────────────────────────────────────────────────

    static String buildMetrics() {
        long req  = requestCount.get();
        long err  = errorCount.get();
        long dbe  = dbErrorCount.get();
        double er = req > 0 ? (double) err / req : 0;
        return String.join("\n",
            "# HELP jvm_orders_total Total orders processed",
            "# TYPE jvm_orders_total counter",
            String.format("jvm_orders_total{service=\"%s\",env=\"%s\"} %d", SERVICE, ENV, req),
            "# HELP jvm_errors_total Total errors",
            "# TYPE jvm_errors_total counter",
            String.format("jvm_errors_total{service=\"%s\",env=\"%s\"} %d", SERVICE, ENV, err),
            "# HELP jvm_error_rate Current error rate",
            "# TYPE jvm_error_rate gauge",
            String.format("jvm_error_rate{service=\"%s\",env=\"%s\"} %.4f", SERVICE, ENV, er),
            "# HELP jvm_db_errors_total DB connection errors",
            "# TYPE jvm_db_errors_total counter",
            String.format("jvm_db_errors_total{service=\"%s\",env=\"%s\"} %d", SERVICE, ENV, dbe),
            "# HELP jvm_leak_objects Leaked objects in cache",
            "# TYPE jvm_leak_objects gauge",
            String.format("jvm_leak_objects{service=\"%s\"} %d", SERVICE, leakMap.size())
        ) + "\n";
    }

    // ── HTTP mini-server ──────────────────────────────────────────────────────

    static void startHttpServer() throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress(PORT), 0);

        server.createContext("/health", ex -> {
            String body = String.format("{\"status\":\"ok\",\"mode\":\"%s\",\"service\":\"%s\"}",
                                        mode, SERVICE);
            ex.sendResponseHeaders(200, body.length());
            ex.getResponseBody().write(body.getBytes());
            ex.close();
        });

        server.createContext("/metrics", ex -> {
            String body = buildMetrics();
            ex.getResponseHeaders().set("Content-Type", "text/plain; version=0.0.4");
            ex.sendResponseHeaders(200, body.length());
            ex.getResponseBody().write(body.getBytes());
            ex.close();
        });

        server.createContext("/simulate/", ex -> {
            String issue = ex.getRequestURI().getPath().replace("/simulate/", "");
            Set<String> valid = new HashSet<>(Arrays.asList(
                "normal","oom","npe","deadlock","connection_pool","gc_pressure","high_latency"
            ));
            if (valid.contains(issue)) {
                mode = issue;
                if ("normal".equals(issue)) leakMap.clear();
                emit("INFO", "c.e.order.SimulationController",
                     "Mode switched to '" + issue + "' by operator");
                String body = String.format("{\"mode\":\"%s\",\"status\":\"activated\"}", issue);
                ex.sendResponseHeaders(200, body.length());
                ex.getResponseBody().write(body.getBytes());
            } else {
                String body = "{\"error\":\"unknown issue\"}";
                ex.sendResponseHeaders(400, body.length());
                ex.getResponseBody().write(body.getBytes());
            }
            ex.close();
        });

        server.setExecutor(Executors.newFixedThreadPool(4));
        server.start();
        emit("INFO", "c.e.order.App",
             String.format("%s v%s HTTP server started on :%d", SERVICE, VERSION, PORT));
    }

    // ── Background log emitter ────────────────────────────────────────────────

    static void runEmitter() {
        while (true) {
            try {
                switch (mode) {
                    case "normal":
                        genNormalOrder();
                        if (rng.nextDouble() < 0.05) genNPE();
                        Thread.sleep((long)(300 + rng.nextGaussian() * 100));
                        break;
                    case "npe":
                        genNormalOrder();
                        genNPE();
                        if (rng.nextDouble() < 0.5) genNPE();
                        Thread.sleep(200);
                        break;
                    case "oom":
                        genOOM();
                        Thread.sleep(100);
                        break;
                    case "connection_pool":
                        genNormalOrder();
                        genConnectionPool();
                        if (rng.nextDouble() < 0.4) genConnectionPool();
                        Thread.sleep(500);
                        break;
                    case "gc_pressure":
                        genNormalOrder();
                        genGCPressure();
                        Thread.sleep(300);
                        break;
                    case "deadlock":
                        genDeadlock();
                        Thread.sleep(2000);
                        break;
                    case "high_latency":
                        genNormalOrder();
                        genHighLatency();
                        Thread.sleep(400);
                        break;
                    default:
                        genNormalOrder();
                        Thread.sleep(500);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            } catch (Exception e) {
                emit("ERROR", "c.e.order.EmitterThread", "Emitter error: " + e.getMessage());
                try { Thread.sleep(1000); } catch (InterruptedException ie) { break; }
            }
        }
    }

    // ── Main ─────────────────────────────────────────────────────────────────

    public static void main(String[] args) throws Exception {
        emit("INFO", "c.e.order.App",
             String.format("Starting %s v%s | env=%s | pid=%d",
                           SERVICE, VERSION, ENV, ProcessHandle.current().pid()));

        startHttpServer();

        Thread emitter = new Thread(LogGenerator::runEmitter, "log-emitter");
        emitter.setDaemon(true);
        emitter.start();

        Runtime.getRuntime().addShutdownHook(new Thread(() ->
            emit("INFO", "c.e.order.App", "Shutdown signal received — goodbye")));

        emitter.join();
    }
}
