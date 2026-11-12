from core.auditoria import auditar_comando
import uuid
from django.core.management.base import BaseCommand, CommandError
from core.respaldos import probar_restauracion
from core.respaldo_crypto import ErrorRespaldo


class Command(BaseCommand):
    help = 'Prueba la copia en un contenedor temporal sin red, sin puertos y sin usar la base operativa como destino.'

    def add_arguments(self, parser):
        parser.add_argument('identificador', type=uuid.UUID)

    @auditar_comando
    def handle(self, *args, **options):
        try:
            resultado = probar_restauracion(options['identificador'])
        except ErrorRespaldo as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(self.style.SUCCESS(f'Restauración aislada comprobada: {resultado["tablas"]} tablas y {resultado["filas"]} filas. Contenedor retirado.'))
