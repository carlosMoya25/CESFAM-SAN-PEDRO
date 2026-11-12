from core.auditoria import auditar_comando
from django.core.management.base import BaseCommand, CommandError
from core.respaldos import crear_respaldo
from core.respaldo_crypto import ErrorRespaldo


class Command(BaseCommand):
    help = 'Crea una copia SQL cifrada; no imprime claves, credenciales ni contenido de la base.'

    def add_arguments(self, parser):
        parser.add_argument('--crear-clave', action='store_true', help='Inicializa una clave nueva si aún no existe; nunca reemplaza una existente.')
        parser.add_argument('--cliente-docker', action='store_true', help='Usa el cliente de la imagen oficial local compatible con el servidor de origen.')

    @auditar_comando
    def handle(self, *args, **options):
        try:
            copia = crear_respaldo(crear_clave=options['crear_clave'], cliente_docker=options['cliente_docker'])
        except ErrorRespaldo as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(self.style.SUCCESS(f'Copia cifrada creada: {copia.pk}. Tamaño: {copia.tamano} bytes. Restauración todavía no verificada.'))
