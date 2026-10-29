from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from .models import CambioPoliticaRespaldos, PoliticaRespaldos
from .respaldo_forms import PoliticaRespaldosForm
from .respaldo_politica import guardar_politica, pendientes_politica


class PoliticaRespaldosTests(TestCase):
    def setUp(self):
        usuarios = get_user_model()
        self.admin = usuarios.objects.create_user(email="admin-politica@example.com", is_superuser=True)
        self.tecnico = usuarios.objects.create_user(email="ti-politica@example.com")
        self.tecnico.groups.add(Group.objects.get_or_create(name="Técnico TI")[0])
        self.otro = usuarios.objects.create_user(email="suplente-politica@example.com")
        self.url = reverse("panel_respaldos")
        self.datos = {"revision": 0, "frecuencia": "DIARIA", "hora": "02:00", "dia_semana": "",
                      "copias_diarias": 7, "copias_semanales": 4, "copias_mensuales": 3,
                      "prueba_cada_dias": 30, "custodio": self.tecnico.pk, "suplente": self.otro.pk,
                      "procedimiento_clave": "Bóveda institucional separada; procedimiento TI-01.",
                      "ubicacion": "MISMA", "proteccion_adicional": "Copia desconectada en otra sede, revisada por TI.",
                      "motivo": "Definición de prueba por el equipo autorizado."}

    def test_get_no_crea_politica_y_usuario_comun_no_accede(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertContains(response, "Política de respaldos")
        self.assertContains(response, "Sin definir")
        self.assertFalse(PoliticaRespaldos.objects.exists())
        self.client.force_login(self.otro)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.datos).status_code, 403)
        self.assertFalse(CambioPoliticaRespaldos.objects.exists())

    def test_tecnico_guarda_definicion_con_historial_sin_ejecutar_tareas(self):
        self.client.force_login(self.tecnico)
        response = self.client.post(self.url, self.datos)
        self.assertEqual(response.status_code, 302)
        politica = PoliticaRespaldos.objects.get()
        self.assertEqual(politica.revision, 1)
        self.assertEqual(politica.copias_diarias, 7)
        self.assertEqual(politica.hora.hour, 2)
        self.assertFalse(pendientes_politica(politica))
        cambio = CambioPoliticaRespaldos.objects.get()
        self.assertEqual(cambio.realizado_por, self.tecnico)
        self.assertEqual(cambio.antes["frecuencia"], "Sin definir")
        self.assertEqual(cambio.despues["frecuencia"], "Diariamente")
        self.assertIn(self.otro.email, cambio.despues["suplente"])
        response = self.client.get(self.url)
        self.assertContains(response, "Programación automática no activada")
        self.assertContains(response, "Definición registrada")
        self.assertIn("no-store", response["Cache-Control"])
        self.client.force_login(self.otro)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_no_permite_sobrescribir_desde_pestana_antigua(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, self.datos)
        self.datos["copias_diarias"] = 12
        response = self.client.post(self.url, self.datos)
        self.assertContains(response, "Otra persona cambió esta política")
        self.assertEqual(PoliticaRespaldos.objects.get().copias_diarias, 7)
        self.assertEqual(CambioPoliticaRespaldos.objects.count(), 1)
        self.datos["revision"] = 1
        self.assertEqual(self.client.post(self.url, self.datos).status_code, 302)
        self.assertEqual(PoliticaRespaldos.objects.get().revision, 2)
        self.assertEqual(CambioPoliticaRespaldos.objects.count(), 2)

    def test_rechaza_custodios_iguales_inactivos_y_valores_fuera_de_rango(self):
        self.otro.is_active = False
        self.otro.save(update_fields=["is_active"])
        form = PoliticaRespaldosForm(self.datos)
        self.assertFalse(form.is_valid())
        self.assertIn("suplente", form.errors)
        for campo, valor in (("suplente", self.tecnico.pk), ("copias_diarias", 366),
                             ("copias_semanales", -1), ("copias_mensuales", 121),
                             ("prueba_cada_dias", 0)):
            datos = {**self.datos, "suplente": "", campo: valor}
            self.assertFalse(PoliticaRespaldosForm(datos).is_valid())

    def test_exige_hora_dia_semanal_y_plan_si_misma_ubicacion(self):
        for cambios, campo in (({"hora": ""}, "hora"),
                               ({"frecuencia": "SEMANAL", "dia_semana": ""}, "dia_semana"),
                               ({"proteccion_adicional": ""}, "proteccion_adicional")):
            form = PoliticaRespaldosForm({**self.datos, **cambios})
            self.assertFalse(form.is_valid())
            self.assertIn(campo, form.errors)
        form = PoliticaRespaldosForm({**self.datos, "frecuencia": "SEMANAL", "dia_semana": 0})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["dia_semana"], 0)

    def test_definicion_parcial_muestra_pendientes_y_cuenta_desactivada(self):
        datos = {**self.datos, "frecuencia": "PENDIENTE", "copias_diarias": "", "copias_semanales": "",
                 "copias_mensuales": "", "prueba_cada_dias": "", "custodio": "", "suplente": "",
                 "procedimiento_clave": "", "ubicacion": "PENDIENTE", "proteccion_adicional": ""}
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(self.url, datos).status_code, 302)
        politica = PoliticaRespaldos.objects.get()
        self.assertEqual(politica.hora.hour, 2)
        self.assertTrue(pendientes_politica(politica))
        self.assertContains(self.client.get(self.url), "Definición parcial")
        politica.custodio = self.tecnico
        politica.suplente = self.otro
        self.otro.is_active = False
        self.otro.save(update_fields=["is_active"])
        self.assertTrue(any("suplente" in p for p in pendientes_politica(politica)))

    def test_guardado_revalida_cuenta_desactivada_despues_del_formulario(self):
        form = PoliticaRespaldosForm(self.datos)
        self.assertTrue(form.is_valid())
        self.otro.is_active = False
        self.otro.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            guardar_politica(usuario=self.admin, datos=form.cleaned_data)
        self.assertFalse(PoliticaRespaldos.objects.exists())
        self.assertFalse(CambioPoliticaRespaldos.objects.exists())

    def test_post_requiere_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        self.assertEqual(cliente.post(self.url, self.datos).status_code, 403)
        self.assertFalse(PoliticaRespaldos.objects.exists())

    def test_dia_y_hora_se_conservan_al_guardar_frecuencia_diaria_o_manual(self):
        self.client.force_login(self.admin)
        for revision, frecuencia in enumerate(("DIARIA", "MANUAL", "SEMANAL")):
            datos = {**self.datos, "revision": revision, "frecuencia": frecuencia, "hora": "23:00", "dia_semana": 0}
            self.assertEqual(self.client.post(self.url, datos).status_code, 302)
            politica = PoliticaRespaldos.objects.get()
            self.assertEqual(politica.dia_semana, 0)
            self.assertEqual(politica.hora.hour, 23)
            response = self.client.get(self.url)
            self.assertEqual(str(response.context["form_politica"]["dia_semana"].value()), "0")
