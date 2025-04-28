from django.shortcuts import render
from django.http import JsonResponse
from sqlalchemy import text
from .db import Session
import requests

# Create your views here.

def search_view(request):
    query = request.GET.get('q')  # Получаем параметр поиска из GET-запроса
    results = []

    if query:
        session = Session()  # Создаем сессию SQLAlchemy
        try:
            # Выполняем SQL-запрос для поиска по базе данных
            sql_query = text("SELECT id, first_name, last_name FROM patients WHERE first_name ILIKE :query OR last_name ILIKE :query")
            rows = session.execute(sql_query, {"query": f"%{query}%"}).fetchall()
            results = [{"id": row[0], "first_name": row[1], "last_name": row[2]} for row in rows]
        finally:
            session.close()  # Закрываем сессию

    # Передаем результаты поиска в шаблон
    return render(request, 'search_form.html', {'results': results})


def get_patient_list(request):
    session = Session()  # Создаем сессию SQLAlchemy
    try:
        # Выполняем SQL-запрос для получения данных из таблицы BMDPAT1
        sql_query = text("SELECT PATIENTID, WMDAID FROM BMDPAT1")
        rows = session.execute(sql_query).fetchall()

        # Преобразуем данные в формат JSON
        patients = [{"patient_id": row[0], "wmda_id": row[1]} for row in rows]
    finally:
        session.close()  # Закрываем сессию

    return JsonResponse({"patients": patients})

def check_patient(request):
    import json
    data = json.loads(request.body)
    patient_id = data.get('patient_id')

    session = Session()
    try:
        sql_query = text("SELECT WMDAID FROM BMDPAT1 WHERE PATIENTID = :patient_id")
        result = session.execute(sql_query, {"patient_id": patient_id}).fetchone()

        if result:
            wmda_id = result[0]
            return JsonResponse({"wmda_id": wmda_id}, status=200)
        else:
            return JsonResponse({"error": "Patient not found"}, status=404)
    finally:
        session.close()

def register_patient(request):
    import json
    data = json.loads(request.body)
    patient_id = data.get('patient_id')

    session = Session()
    try:
        # Получаем данные для запроса
        sql_query = text("""
            SELECT BMDPAT1.PATIENTID, BMDPAT3.DNAA1, BMDPAT3.DNAB1, BMDPAT3.DRB11
            FROM BMDPAT1
            JOIN BMDPAT3 ON BMDPAT1.PATIENTNUM = BMDPAT3.PATIENTNUM
            WHERE BMDPAT1.PATIENTID = :patient_id
        """)
        result = session.execute(sql_query, {"patient_id": patient_id}).fetchone()

        if not result:
            return JsonResponse({"error": "Patient not found"}, status=404)

        # Формируем запрос к внешнему API
        payload = {
            "patientId": result[0],
            "hla": {
                "a": {"field1": result[1]},
                "b": {"field1": result[2]},
                "drb1": {"field1": result[3]},
            },
        }

        # Отправляем запрос к внешнему API
        response = requests.post(
            "https://sandbox-search-api.wmda.info/api/v2/patients",
            json=payload,
        )

        if response.status_code == 200:
            external_response = response.json()
            wmda_id = external_response.get("wmdaId")

            # Обновляем значение WMDAID в базе данных
            update_query = text("UPDATE BMDPAT1 SET WMDAID = :wmda_id WHERE PATIENTID = :patient_id")
            session.execute(update_query, {"wmda_id": wmda_id, "patient_id": patient_id})
            session.commit()

            return JsonResponse({"success": True, "wmda_id": wmda_id}, status=200)
        else:
            return JsonResponse({"error": "Failed to register patient with external API"}, status=500)

    finally:
        session.close()