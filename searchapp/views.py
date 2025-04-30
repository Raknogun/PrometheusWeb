from django.shortcuts import render
from django.http import JsonResponse
from sqlalchemy import text
from .db import Session
import requests
import json
from django.views.decorators.csrf import csrf_exempt

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
        sql_query = text("SELECT PATIENTID, WMDAID_SM FROM BMDPAT1")
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
        sql_query = text("SELECT WMDAID_SM FROM BMDPAT1 WHERE PATIENTID = :patient_id")
        result = session.execute(sql_query, {"patient_id": patient_id}).fetchone()

        if result:
            wmda_id = result[0]
            return JsonResponse({"wmda_id": wmda_id}, status=200)
        else:
            return JsonResponse({"error": "Patient not found"}, status=404)
    finally:
        session.close()

@csrf_exempt
def register_patient(request):
    print("Функция register_patient вызвана")

    try:
        # Чтение данных из тела запроса
        data = json.loads(request.body)
        patient_id = data.get('patient_id')
        print(f"Получен patient_id: {patient_id}")

        if not patient_id:
            print("patient_id отсутствует в запросе")
            return JsonResponse({"error": "patient_id is required"}, status=400)

        # Подключение к базе данных
        session = Session()

        try:
            # Получение данных пациента из базы
            sql_query = text("""
                SELECT BMDPAT1.PATIENTID, BMDPAT3.DNAA1, BMDPAT3.DNAB1, BMDPAT3.DRB11
                FROM BMDPAT1
                JOIN BMDPAT3 ON BMDPAT1.PATIENTNUM = BMDPAT3.PATIENTNUM
                WHERE BMDPAT1.PATIENTID = :patient_id
            """)
            result = session.execute(sql_query, {"patient_id": patient_id}).fetchone()

            if not result:
                print(f"Пациент с patient_id {patient_id} не найден в базе данных")
                return JsonResponse({"error": "Patient not found"}, status=404)

            print(f"Данные пациента из базы: {result}")
        except Exception as e:
            print(f"Ошибка при выполнении SQL-запроса: {e}")
            return JsonResponse({"error": "Database query failed"}, status=500)
        finally:
            session.close()

        # Формирование payload для внешнего API
        payload = {
            "patientId": result[0],
            "hla": {
                "a": {"field1": result[1]},
                "b": {"field1": result[2]},
                "drb1": {"field1": result[3]},
            },
        }
        print(f"Payload для внешнего API: {json.dumps(payload, indent=2)}")

        # Отправка запроса к внешнему API
        url = "https://sandbox-search-api.wmda.info/api/v2/patients"
        headers = {
            "Authorization": "Bearer YOUR_API_TOKEN",  # Добавьте токен, если требуется
            "Content-Type": "application/json",
        }
        print(f"Отправка запроса на URL: {url}")
        print(f"Заголовки запроса: {headers}")

        try:
            # Отправляем запрос и выводим ответ
            response = requests.post(url, json=payload, headers=headers)
            print(f"Ответ от внешнего API: статус {response.status_code}")
            if response.text:
                print(f"Тело ответа: {response.text}")

            # Проверяем статус ответа
            if response.status_code == 200:
                external_response = response.json()
                wmda_id = external_response.get("wmdaId")
                print(f"Получен wmda_id из внешнего API: {wmda_id}")

                # Обновление базы данных
                session = Session()
                update_query = text("""
                    UPDATE BMDPAT1 
                    SET WMDAID_SM = :wmda_id 
                    WHERE PATIENTID = :patient_id
                """)
                session.execute(update_query, {"wmda_id": wmda_id, "patient_id": patient_id})
                session.commit()
                print("Данные успешно обновлены в базе данных")
                return JsonResponse({"success": True, "wmda_id": wmda_id}, status=200)
            else:
                print(f"Ошибка при регистрации пациента во внешнем API. Код ответа: {response.status_code}, Тело: {response.text}")
                return JsonResponse({"error": f"Failed to register patient with external API. Код ответа: {response.status_code}"}, status=response.status_code)
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при отправке запроса к внешнему API: {e}")
            return JsonResponse({"error": "External API request failed"}, status=500)
    except json.JSONDecodeError:
        print("Ошибка разбора JSON")
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        print(f"Необработанная ошибка в функции register_patient: {e}")
        return JsonResponse({"error": "Internal server error"}, status=500)