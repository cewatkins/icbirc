#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <errno.h>

#define BUFFER_SIZE 4096

typedef struct {
    int socket;
    char *server;
    int port;
    char *nickname;
    char *group;
    char *logid;
} IcbConn;

typedef struct {
    char *icb_server;
    int icb_port;
    char *irc_server;
    int irc_port;
    char *irc_channel;
    char *nickname;
    char *icb_channel;
    int shutting_down;
    IcbConn *icb_conn;
    int irc_socket;
} ICBIRCBridge;

void *ping_icb(void *arg);
void *ping_irc(void *arg);
void *receive_from_icb(void *arg);
void *receive_from_irc(void *arg);

void icb_connect(IcbConn *conn) {
    struct sockaddr_in server_addr;

    conn->socket = socket(AF_INET, SOCK_STREAM, 0);
    if (conn->socket < 0) {
        perror("Socket creation failed");
        exit(EXIT_FAILURE);
    }

    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(conn->port);
    inet_pton(AF_INET, conn->server, &server_addr.sin_addr);

    if (connect(conn->socket, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        perror("Connection to ICB server failed");
        exit(EXIT_FAILURE);
    }
}

void icb_send(IcbConn *conn, const char *msg) {
    send(conn->socket, msg, strlen(msg), 0);
}

void icb_login(IcbConn *conn) {
    char login_msg[BUFFER_SIZE];
    snprintf(login_msg, sizeof(login_msg), "a%s%s%slogin", conn->logid, conn->nickname, conn->group);
    icb_send(conn, login_msg);
}

void icb_close(IcbConn *conn) {
    close(conn->socket);
}

void *ping_icb(void *arg) {
    ICBIRCBridge *bridge = (ICBIRCBridge *)arg;
    while (!bridge->shutting_down) {
        icb_send(bridge->icb_conn, "l");
        sleep(60);
    }
    return NULL;
}

void *ping_irc(void *arg) {
    ICBIRCBridge *bridge = (ICBIRCBridge *)arg;
    while (!bridge->shutting_down) {
        send(bridge->irc_socket, "PING :ping\r\n", strlen("PING :ping\r\n"), 0);
        sleep(60);
    }
    return NULL;
}

void *receive_from_icb(void *arg) {
    ICBIRCBridge *bridge = (ICBIRCBridge *)arg;
    char buffer[BUFFER_SIZE];
    while (!bridge->shutting_down) {
        int len = recv(bridge->icb_conn->socket, buffer, sizeof(buffer), 0);
        if (len > 0) {
            buffer[len] = '\0';
            printf("Received from ICB: %s\n", buffer);
            // Process and forward to IRC
        }
    }
    return NULL;
}

void *receive_from_irc(void *arg) {
    ICBIRCBridge *bridge = (ICBIRCBridge *)arg;
    char buffer[BUFFER_SIZE];
    while (!bridge->shutting_down) {
        int len = recv(bridge->irc_socket, buffer, sizeof(buffer), 0);
        if (len > 0) {
            buffer[len] = '\0';
            printf("Received from IRC: %s\n", buffer);
            // Process and forward to ICB
        }
    }
    return NULL;
}

void connect_icb(ICBIRCBridge *bridge) {
    while (!bridge->shutting_down) {
        bridge->icb_conn = malloc(sizeof(IcbConn));
        bridge->icb_conn->server = bridge->icb_server;
        bridge->icb_conn->port = bridge->icb_port;
        bridge->icb_conn->nickname = bridge->nickname;
        bridge->icb_conn->group = "1";
        bridge->icb_conn->logid = bridge->nickname;

        icb_connect(bridge->icb_conn);
        icb_login(bridge->icb_conn);

        pthread_t icb_ping_thread, icb_recv_thread;
        pthread_create(&icb_ping_thread, NULL, ping_icb, bridge);
        pthread_create(&icb_recv_thread, NULL, receive_from_icb, bridge);
        break;
    }
}

void connect_irc(ICBIRCBridge *bridge) {
    struct sockaddr_in server_addr;

    while (!bridge->shutting_down) {
        bridge->irc_socket = socket(AF_INET, SOCK_STREAM, 0);
        if (bridge->irc_socket < 0) {
            perror("Socket creation failed");
            exit(EXIT_FAILURE);
        }

        server_addr.sin_family = AF_INET;
        server_addr.sin_port = htons(bridge->irc_port);
        inet_pton(AF_INET, bridge->irc_server, &server_addr.sin_addr);

        if (connect(bridge->irc_socket, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
            perror("Connection to IRC server failed");
            exit(EXIT_FAILURE);
        }

        char nick_msg[BUFFER_SIZE];
        snprintf(nick_msg, sizeof(nick_msg), "NICK %s\r\n", bridge->nickname);
        send(bridge->irc_socket, nick_msg, strlen(nick_msg), 0);

        char user_msg[BUFFER_SIZE];
        snprintf(user_msg, sizeof(user_msg), "USER %s 0 * :ICB to IRC Gateway\r\n", bridge->nickname);
        send(bridge->irc_socket, user_msg, strlen(user_msg), 0);

        char join_msg[BUFFER_SIZE];
        snprintf(join_msg, sizeof(join_msg), "JOIN %s\r\n", bridge->irc_channel);
        send(bridge->irc_socket, join_msg, strlen(join_msg), 0);

        pthread_t irc_ping_thread, irc_recv_thread;
        pthread_create(&irc_ping_thread, NULL, ping_irc, bridge);
        pthread_create(&irc_recv_thread, NULL, receive_from_irc, bridge);
        break;
    }
}

void start_bridge(ICBIRCBridge *bridge) {
    connect_irc(bridge);
    connect_icb(bridge);
}

void shutdown_bridge(ICBIRCBridge *bridge) {
    bridge->shutting_down = 1;
    icb_close(bridge->icb_conn);
    close(bridge->irc_socket);
}

int main() {
    ICBIRCBridge bridge;
    bridge.icb_server = "default.icb.net";
    bridge.icb_port = 7326;
    bridge.irc_server = "irc.libera.chat";
    bridge.irc_port = 6667;
    bridge.irc_channel = "#ddial2";
    bridge.nickname = "icbircgw";
    bridge.icb_channel = "zzzddial";
    bridge.shutting_down = 0;

    start_bridge(&bridge);

    // Wait for user to terminate
    getchar();

    shutdown_bridge(&bridge);

    return 0;
}