import java.util.ArrayList;
import java.util.List;

/**
 * Demo app that leaks memory at 2MB/sec until the JVM OOMKills.
 * With -Xmx64m this crashes in ~30 seconds.
 * Kubernetes sees OOMKilled exit code → CrashLoopBackOff → Prometheus alert.
 */
public class OomApp {
    public static void main(String[] args) throws Exception {
        System.out.println("[OOM-DEMO] Starting memory leak simulation...");
        System.out.println("[OOM-DEMO] Heap limit: " +
            Runtime.getRuntime().maxMemory() / (1024 * 1024) + "MB");

        List<byte[]> leak = new ArrayList<>();
        int iteration = 0;

        while (true) {
            // Allocate 2MB per iteration
            leak.add(new byte[2 * 1024 * 1024]);
            iteration++;
            long usedMB = (Runtime.getRuntime().totalMemory()
                         - Runtime.getRuntime().freeMemory()) / (1024 * 1024);
            System.out.printf("[OOM-DEMO] iteration=%d used=%dMB%n", iteration, usedMB);
            Thread.sleep(500);
        }
    }
}
