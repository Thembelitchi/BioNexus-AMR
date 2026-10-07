package emb;

import java.nio.file.Path;
import java.util.List;
import org.neo4j.configuration.GraphDatabaseSettings;
import org.neo4j.configuration.connectors.BoltConnector;
import org.neo4j.configuration.helpers.SocketAddress;
import org.neo4j.dbms.api.DatabaseManagementServiceBuilder;

/**
 * Starts an unauthenticated, unencrypted Neo4j on 127.0.0.1 for tests.
 *
 * <p>Usage: {@code Main <home-dir> <plugin-dir> [port]}. GDS procedures are
 * discovered from jars in the plugin directory; their dependencies resolve
 * through the application classpath.
 */
public final class Main {
  public static void main(String[] args) throws Exception {
    if (args.length < 2) {
      System.err.println("usage: Main <home-dir> <plugin-dir> [port]");
      System.exit(64);
    }
    int port = args.length > 2 ? Integer.parseInt(args[2]) : 7687;
    var dbms = new DatabaseManagementServiceBuilder(Path.of(args[0]))
        .setConfig(BoltConnector.enabled, true)
        .setConfig(BoltConnector.listen_address, new SocketAddress("127.0.0.1", port))
        .setConfig(BoltConnector.encryption_level, BoltConnector.EncryptionLevel.DISABLED)
        .setConfig(GraphDatabaseSettings.auth_enabled, false)
        .setConfig(GraphDatabaseSettings.plugin_dir, Path.of(args[1]).toAbsolutePath())
        .setConfig(GraphDatabaseSettings.procedure_unrestricted, List.of("gds.*"))
        .build();
    Runtime.getRuntime().addShutdownHook(new Thread(dbms::shutdown));
    System.out.println("NEO4J READY on bolt://127.0.0.1:" + port);
    Thread.currentThread().join();
  }
}
