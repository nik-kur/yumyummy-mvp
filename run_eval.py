#!/usr/bin/env python3
"""
Скрипт для оценки workflow агента.
Прогоняет промпты из CSV файла через /agent/run endpoint и сохраняет результаты.

Использование:
    python run_eval.py                # Все промпты
    python run_eval.py --limit 10     # Только первые 10 промптов
    python run_eval.py --concurrency 3  # 3 параллельных запроса
"""
import csv
import json
import asyncio
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict

import httpx

# Конфигурация
CSV_FILE = "yumyummy_eval_cases_100.csv"
OUTPUT_FILE = "eval_results.json"
BACKEND_URL = "http://127.0.0.1:8000"
TELEGRAM_ID = "eval_test_user"
TIMEOUT = 180.0  # секунд, как в проде
MAX_CONCURRENT = 5  # максимальное количество параллельных запросов по умолчанию
RETRY_ATTEMPTS = 2  # количество попыток при ошибке


async def run_single_prompt(
    client: httpx.AsyncClient,
    telegram_id: str,
    text: str,
    expected_intent: str,
    index: int,
    total: int,
    semaphore: asyncio.Semaphore,
) -> Dict[str, Any]:
    """
    Выполнить один промпт через API.
    """
    result = {
        "index": index + 1,
        "input_text": text,
        "expected_intent": expected_intent,
        "actual_intent": None,
        "response": None,
        "timestamp": datetime.now().isoformat(),
        "success": False,
        "error": None,
        "duration_ms": None,
    }
    
    url = f"{BACKEND_URL}/agent/run"
    payload = {
        "telegram_id": telegram_id,
        "text": text,
    }
    
    async with semaphore:
        print(f"[{index + 1}/{total}] Обработка: {text[:50]}...")
        
        for attempt in range(RETRY_ATTEMPTS + 1):
            try:
                start_time = datetime.now()
                response = await client.post(url, json=payload, timeout=TIMEOUT)
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                result["duration_ms"] = round(duration_ms, 2)
                
                if response.status_code == 200:
                    response_data = response.json()
                    result["success"] = True
                    result["actual_intent"] = response_data.get("intent", "unknown")
                    result["response"] = response_data
                    
                    intent_match = "✓" if result["actual_intent"] == expected_intent else "✗"
                    print(f"[{index + 1}/{total}] {intent_match} intent={result['actual_intent']} (expected={expected_intent}) [{duration_ms:.0f}ms]")
                    return result
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    if attempt < RETRY_ATTEMPTS:
                        print(f"[{index + 1}/{total}] Retry {attempt + 1}/{RETRY_ATTEMPTS}: {error_msg}")
                        await asyncio.sleep(1)
                        continue
                    result["error"] = error_msg
                    print(f"[{index + 1}/{total}] ✗ Ошибка: {error_msg}")
                    return result
                    
            except httpx.ReadTimeout:
                error_msg = "Request timeout"
                if attempt < RETRY_ATTEMPTS:
                    print(f"[{index + 1}/{total}] Retry {attempt + 1}/{RETRY_ATTEMPTS}: timeout")
                    await asyncio.sleep(2)
                    continue
                result["error"] = error_msg
                print(f"[{index + 1}/{total}] ✗ Таймаут")
                return result
                
            except httpx.ConnectError as e:
                error_msg = f"Connection error: {str(e)}"
                if attempt < RETRY_ATTEMPTS:
                    print(f"[{index + 1}/{total}] Retry {attempt + 1}/{RETRY_ATTEMPTS}: connection error")
                    await asyncio.sleep(2)
                    continue
                result["error"] = error_msg
                print(f"[{index + 1}/{total}] ✗ Ошибка подключения: {e}")
                return result
                
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                if attempt < RETRY_ATTEMPTS:
                    print(f"[{index + 1}/{total}] Retry {attempt + 1}/{RETRY_ATTEMPTS}: {error_msg}")
                    await asyncio.sleep(1)
                    continue
                result["error"] = error_msg
                print(f"[{index + 1}/{total}] ✗ Неожиданная ошибка: {e}")
                return result
    
    return result


def read_csv_file(csv_path: Path) -> List[Dict[str, str]]:
    """
    Прочитать CSV файл с промптами.
    """
    prompts = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row.get("input_as_text", "").strip()
            expected_intent = row.get("expected_intent", "").strip()
            if text:
                prompts.append({
                    "text": text,
                    "expected_intent": expected_intent,
                })
    return prompts


def save_results(results: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Сохранить результаты в JSON файл.
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def print_statistics(results: List[Dict[str, Any]]) -> None:
    """
    Вывести статистику по результатам.
    """
    total = len(results)
    successful = sum(1 for r in results if r.get("success", False))
    failed = total - successful
    
    print("\n" + "="*60)
    print("СТАТИСТИКА ВЫПОЛНЕНИЯ")
    print("="*60)
    print(f"Всего промптов: {total}")
    print(f"Успешных: {successful} ({successful/total*100:.1f}%)")
    print(f"Ошибок: {failed} ({failed/total*100:.1f}%)")
    
    if successful > 0:
        # Распределение интентов
        intent_counts = defaultdict(int)
        intent_matches = defaultdict(lambda: {"correct": 0, "total": 0})
        
        for r in results:
            if r.get("success"):
                actual = r.get("actual_intent", "unknown")
                expected = r.get("expected_intent", "")
                intent_counts[actual] += 1
                intent_matches[expected]["total"] += 1
                if actual == expected:
                    intent_matches[expected]["correct"] += 1
        
        print("\nРаспределение полученных интентов (actual):")
        for intent, count in sorted(intent_counts.items(), key=lambda x: -x[1]):
            print(f"  {intent}: {count}")
        
        # Точность по expected интентам
        print("\nТочность по ожидаемым интентам (expected):")
        total_correct = 0
        total_expected = 0
        for expected, stats in sorted(intent_matches.items()):
            if stats["total"] > 0:
                accuracy = stats["correct"] / stats["total"] * 100
                print(f"  {expected}: {stats['correct']}/{stats['total']} ({accuracy:.1f}%)")
                total_correct += stats["correct"]
                total_expected += stats["total"]
        
        if total_expected > 0:
            overall_accuracy = total_correct / total_expected * 100
            print(f"\nОбщая точность: {total_correct}/{total_expected} ({overall_accuracy:.1f}%)")
        
        # Среднее время
        durations = [r["duration_ms"] for r in results if r.get("duration_ms")]
        if durations:
            avg_duration = sum(durations) / len(durations)
            print(f"\nСреднее время ответа: {avg_duration:.0f}ms")
        
    # Ошибки по типам
    if failed > 0:
        error_types = defaultdict(int)
        for r in results:
            if not r.get("success"):
                error = r.get("error", "Unknown error")
                error_type = error.split(":")[0] if ":" in error else error
                error_types[error_type] += 1
        
        print("\nТипы ошибок:")
        for error_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
            print(f"  {error_type}: {count}")
    
    print("="*60)


async def check_backend_health() -> bool:
    """
    Проверить доступность backend.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BACKEND_URL}/health", timeout=5.0)
            if response.status_code == 200:
                return True
    except Exception:
        pass
    return False


async def main(csv_file: str = CSV_FILE, limit: Optional[int] = None, concurrency: int = MAX_CONCURRENT):
    """
    Основная функция.
    """
    csv_path = Path(csv_file)
    # Output file name based on input file
    output_path = Path(csv_path.stem + "_results.json")
    
    # Проверка существования CSV файла
    if not csv_path.exists():
        print(f"Ошибка: файл {CSV_FILE} не найден!")
        sys.exit(1)
    
    # Проверка доступности backend
    print(f"Проверка доступности backend ({BACKEND_URL})...")
    if not await check_backend_health():
        print(f"\nОшибка: backend недоступен на {BACKEND_URL}")
        print("Убедитесь, что backend запущен:")
        print("  python3 -m uvicorn app.main:app --reload")
        sys.exit(1)
    print("Backend доступен ✓\n")
    
    # Чтение промптов из CSV
    print(f"Чтение промптов из {CSV_FILE}...")
    all_prompts = read_csv_file(csv_path)
    
    # Ограничение количества промптов
    if limit is not None and limit > 0:
        prompts = all_prompts[:limit]
        print(f"Обработка первых {limit} из {len(all_prompts)} промптов")
    else:
        prompts = all_prompts
        print(f"Обработка всех {len(prompts)} промптов")
    
    total_prompts = len(prompts)
    
    if total_prompts == 0:
        print("Ошибка: не найдено промптов в CSV файле!")
        sys.exit(1)
    
    print(f"Параллельных запросов: {concurrency}")
    print(f"Таймаут: {TIMEOUT} секунд")
    print(f"Telegram ID: {TELEGRAM_ID}")
    print("\nНачинаю выполнение...\n")
    
    # Выполнение запросов
    all_results = []
    semaphore = asyncio.Semaphore(concurrency)
    
    async with httpx.AsyncClient() as client:
        tasks = [
            run_single_prompt(
                client=client,
                telegram_id=TELEGRAM_ID,
                text=prompt["text"],
                expected_intent=prompt["expected_intent"],
                index=i,
                total=total_prompts,
                semaphore=semaphore,
            )
            for i, prompt in enumerate(prompts)
        ]
        
        # Выполняем все задачи и собираем результаты
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обработка исключений
        processed_results = []
        for i, result in enumerate(all_results):
            if isinstance(result, Exception):
                processed_results.append({
                    "index": i + 1,
                    "input_text": prompts[i]["text"],
                    "expected_intent": prompts[i]["expected_intent"],
                    "actual_intent": None,
                    "response": None,
                    "timestamp": datetime.now().isoformat(),
                    "success": False,
                    "error": f"Exception: {str(result)}",
                    "duration_ms": None,
                })
            else:
                processed_results.append(result)
        
        all_results = processed_results
    
    # Сохранение результатов
    save_results(all_results, output_path)
    print(f"\nРезультаты сохранены в {OUTPUT_FILE}")
    
    # Вывод статистики
    print_statistics(all_results)
    
    print(f"\nГотово! Результаты в {OUTPUT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Оценка workflow агента через прогон промптов из CSV"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=CSV_FILE,
        help=f"Путь к CSV файлу с промптами (по умолчанию {CSV_FILE})"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Обработать только первые N промптов (по умолчанию - все)"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=MAX_CONCURRENT,
        help=f"Количество параллельных запросов (по умолчанию {MAX_CONCURRENT})"
    )
    
    args = parser.parse_args()
    asyncio.run(main(csv_file=args.csv, limit=args.limit, concurrency=args.concurrency))
