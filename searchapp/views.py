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

@csrf_exempt
def start_search(request):
    """
    Handles the "Start search" button functionality.
    """
    try:
        # Extract data from the POST request
        data = json.loads(request.body)
        patient_id = data.get('patient_id')
        search_engine = data.get('search_engine')  # hap-e or atlas
        search_type = data.get('search_type')  # ABDR or CB

        if not patient_id:
            return JsonResponse({"error": "Patient ID is required."}, status=400)

        session = Session()
        try:
            # Check if WMDAID is available for the patient
            sql_query = text("SELECT PATIENTNUM, WMDAID_SM FROM BMDPAT1 WHERE PATIENTID = :patient_id")
            patient = session.execute(sql_query, {"patient_id": patient_id}).fetchone()

            if not patient:
                return JsonResponse({"error": "Patient not found."}, status=404)

            patientnum, wmda_id = patient
            if not wmda_id or wmda_id == 0:
                return JsonResponse({"error": "The selected patient is not registered and does not have a valid WMDAID."}, status=400)

            # Prepare data for the external API
            match_engine = 2 if search_engine == "hap-e" else 3
            search_type_api = "DR" if search_type == "ABDR" else "CB"
            payload = {
                "wmdaId": wmda_id,
                "matchEngine": match_engine,
                "searchType": search_type_api,
                "OverallMismatches": 0
            }

            # Send data to the external API
            api_url = "https://example.com/api/search"  # Replace with the actual API URL
            headers = {"Content-Type": "application/json"}
            response = requests.post(api_url, json=payload, headers=headers)

            if response.status_code != 200:
                return JsonResponse({"error": "Failed to initiate search with external API."}, status=response.status_code)

            # Extract searchId from the API response
            search_id = response.json().get("searchId")
            if not search_id:
                return JsonResponse({"error": "Invalid response from external API."}, status=500)

            # Insert the result into the Firebird database (BMDSRCID table)
            insert_query = text("""
                INSERT INTO BMDSRCID (SRCNUM, PATIENTNUM, SEARCHID, SRCENGINE, SRCTYPE, STATUS)
                VALUES (
                    (SELECT COALESCE(MAX(SRCNUM), 0) + 1 FROM BMDSRCID),
                    :patientnum,
                    :search_id,
                    :srcengine,
                    :srctype,
                    0
                )
            """)
            session.execute(insert_query, {
                "patientnum": patientnum,
                "search_id": search_id,
                "srcengine": match_engine,
                "srctype": search_type_api
            })
            session.commit()

        finally:
            session.close()

        return JsonResponse({"success": True, "searchId": search_id}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def search_form(request):
    return render(request, 'search_form.html')

def patient_form(request):
    return render(request, 'Patient_form.html')