"""Serveur TCP experimental conserve hors du parcours solo principal.

Ce module reste volontairement separe de l'application principale,
qui se concentre desormais sur une experience solo stable et livrable.
"""

import socket
import threading

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

IP = "0.0.0.0"  # Ajuster l'adresse si vous testez sur un reseau local specifique.
PORT = 12345

server.bind((IP, PORT))
server.listen(5)

clients = []
client_names = {}


def handle_client(client):
    while True:
        try:
            message = client.recv(1024).decode("utf-8")
            if message:
                broadcast(client, message)
        except Exception:
            remove_client(client, "has left the game.")
            break


def broadcast(sender, message):
    for client in clients:
        if client != sender:
            try:
                client.send(message.encode("utf-8"))
            except Exception:
                remove_client(client, "has disconnected unexpectedly.")


def remove_client(client, suffix):
    if client in clients:
        clients.remove(client)
    name = client_names.pop(client, "Unknown player")
    try:
        client.close()
    finally:
        broadcast(None, f"{name} {suffix}")


def accept_connections():
    while True:
        client, addr = server.accept()
        clients.append(client)
        name = client.recv(1024).decode("utf-8")
        client_names[client] = name
        print(f"{name} connected with {addr}")
        broadcast(None, f"{name} has joined the game.")
        threading.Thread(target=handle_client, args=(client,), daemon=True).start()


if __name__ == "__main__":
    print("Server is listening...")
    accept_connections()
