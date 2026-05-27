"""Concrete ``MessagenetSipGatewayClient`` implementations.

Each module here is a self-contained backend (Asterisk ARI, 3CX, etc.).
Selection happens at startup via :func:`messagenet.wiring.install_messagenet_gateway`;
nothing in the provider itself imports a specific backend.
"""
