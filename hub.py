import argparse

from comandos.iniciar import iniciar
from comandos.parar import parar
from comandos.status import status

parser = argparse.ArgumentParser(description="HUB Manager")

parser.add_argument(
    "comando",
    choices=["iniciar", "parar", "status"]
)

args = parser.parse_args()

if args.comando == "iniciar":
    iniciar()

elif args.comando == "parar":
    parar()

elif args.comando == "status":
    status()