from core.auditoria import auditar_comando
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, close_old_connections
from core.respaldo_crypto import ErrorRespaldo
from core.respaldo_programacion import ejecutar_turno


class Command(BaseCommand):
    help = "Comprueba la programación y genera, como máximo, una copia SQL cifrada por turno."

    def add_arguments(self, parser):
        parser.add_argument("--continuo", action="store_true", help="Comprueba la política cada 60 segundos hasta detener el proceso.")
        parser.add_argument("--cliente-docker", action="store_true", help="Usa el cliente oficial local de Docker ya disponible.")

    @auditar_comando
    def handle(self, *args, **options):
        try:
            while True:
                close_old_connections()
                try:
                    resultado = ejecutar_turno(cliente_docker=options["cliente_docker"])
                except ErrorRespaldo as exc:
                    raise CommandError(str(exc)) from None
                except DatabaseError:
                    if not options["continuo"]:
                        raise CommandError("No se pudo consultar o registrar la programación en la base configurada.") from None
                    resultado = "Base no disponible para la programación; se volverá a comprobar en 60 segundos."
                self.stdout.write(resultado)
                if not options["continuo"]:
                    break
                time.sleep(60)
        except KeyboardInterrupt:
            self.stdout.write("Ejecutor detenido. Si había una copia en curso, revisa su estado en el panel.")
