import collections

from bson.son import SON

from ..database import db
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from ..config.config import config
from fastapi import HTTPException
from starlette import status


class MetricServiceByTenant:

    @staticmethod
    def get_monthly_usage_old():
        def zero_pad(m):
            return str(m) if m >= 10 else "0" + str(m)

        tenant_id = config.user_info_var.get()["tenant_id"]
        if not tenant_id:
            return []

        pipeline = [
            {"$match": {"tenant_id": tenant_id}},
            {
                "$project": {
                    "year": {"$year": "$datetime"},
                    "month": {"$month": "$datetime"},
                    "tenant_id": 1,
                }
            },
            {
                "$group": {
                    "_id": {"year": "$year", "month": "$month"},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": SON([("_id.year", -1), ("_id.month", -1)])},
        ]

        result = db.usage_log.aggregate(pipeline)
        response = [
            {
                "month": f"{item['_id']['year']}/{zero_pad(item['_id']['month'])}",
                "count": item["count"],
            }
            for item in result
        ]
        return response

    @staticmethod
    def get_monthly_usage():
        def zero_pad(m):
            return str(m) if m >= 10 else "0" + str(m)

        tenant_id = config.user_info_var.get()["tenant_id"]
        if not tenant_id:
            return []

        # Calculate the date 6 months ago
        today = datetime.today()
        six_months_ago = today - timedelta(
            days=6 * 30
        )  # Approximate 6 months as 180 days

        # Extract year and month from the current date and 6 months ago
        six_months_ago_year = six_months_ago.year
        six_months_ago_month = six_months_ago.month

        # MongoDB aggregation pipeline
        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"year": {"$gt": six_months_ago_year}},
                        {
                            "year": six_months_ago_year,
                            "month": {"$gte": six_months_ago_month},
                        },
                    ],
                    "tenant_id": tenant_id,
                }
            },
            {
                "$group": {
                    "_id": {"year": "$year", "month": "$month"},
                    "count": {"$sum": "$count"},
                }
            },
            {"$sort": SON([("_id.year", -1), ("_id.month", -1)])},
        ]

        # Query the users_usage collection
        result = db.users_usage.aggregate(pipeline)

        # Format the response
        response = [
            {
                "month": f"{item['_id']['year']}/{zero_pad(item['_id']['month'])}",
                "count": item["count"],
            }
            for item in result
        ]

        return response

    @staticmethod
    def get_monthly_usage_current():
        tenant_id = config.user_info_var.get()["tenant_id"]
        if not tenant_id:
            return 0

        # Get the current year and month
        now = datetime.now()
        current_year = now.year
        current_month = now.month

        # Calculate the start and end of the current month
        start_of_month = datetime(current_year, current_month, 1)
        if current_month == 12:
            end_of_month = datetime(current_year + 1, 1, 1)
        else:
            end_of_month = datetime(current_year, current_month + 1, 1)

        # Define the aggregation pipeline
        pipeline = [
            {
                "$match": {
                    "datetime": {"$gte": start_of_month, "$lt": end_of_month},
                    "tenant_id": tenant_id,
                }
            },
            {
                "$group": {
                    "_id": None,  # Grouping without specific field since we want total count
                    "count": {"$sum": 1},
                }
            },
        ]
        # Execute the aggregation pipeline
        result = db.usage_log.aggregate(pipeline)
        count = next(result, {}).get(
            "count", 0
        )  # Get the count or default to 0 if no documents
        return count

    @staticmethod
    def get_models_by_month():
        # Calculate the date for 3 months ago
        tenant_id = config.user_info_var.get()["tenant_id"]
        if not tenant_id:
            return 0

        now = datetime.today()
        three_months_ago_start = (now.replace(day=1) - relativedelta(months=3)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Aggregation pipeline
        pipeline = [
            {
                "$match": {
                    "datetime": {
                        "$gte": three_months_ago_start  # Filter for the last 3 months
                    },
                    "tenant_id": tenant_id,
                }
            },
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$datetime"},  # Extract year from datetime
                        "month": {"$month": "$datetime"},  # Extract month from datetime
                        "model": "$meta.model",  # Group by model name
                    },
                    "count": {"$sum": 1},  # Count the number of entries
                }
            },
            {
                "$sort": {
                    "_id.year": -1,  # Sort by year
                    "_id.month": -1,  # Sort by month
                    "_id.model": 1,  # Sort by model name
                }
            },
        ]

        # Execute the aggregation query
        result = list(db.usage_log.aggregate(pipeline))
        result.sort(
            key=lambda d: (d["_id"]["year"], d["_id"]["month"], d["count"]),
            reverse=True,
        )
        return result

    @staticmethod
    def get_daily_usage():
        tenant_id = config.user_info_var.get()["tenant_id"]
        if not tenant_id:
            return 0

        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        # Aggregation pipeline to group by day and count documents
        pipeline = [
            {
                "$match": {
                    "datetime": {"$gte": seven_days_ago},
                    "tenant_id": tenant_id,
                }
            },
            {
                "$group": {
                    "_id": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$datetime"}
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": -1}},
        ]

        # Execute the aggregation query
        results = list(db.usage_log.aggregate(pipeline))
        return results

    @staticmethod
    def get_daily_usage_all_tenants():
        if not config.user_info_var.get()["is_manager"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
            )

        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        today = datetime.utcnow()

        # Generate a list of the past 7 days in the format "YYYY-MM-DD"
        past_7_days = [
            (today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)
        ]
        # print('past_7_days', past_7_days)
        # past_7_days.reverse()
        # print('past_7_days (reversed)', past_7_days)

        # Aggregation pipeline to group by day and count documents
        pipeline = [
            {"$match": {"datetime": {"$gte": seven_days_ago}}},
            {
                "$group": {
                    "_id": {
                        "date": {
                            "$dateToString": {"format": "%Y-%m-%d", "date": "$datetime"}
                        },
                        "tenant_id": "$tenant_id",
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id.tenant_id": 1, "_id.date": -1}},
        ]

        results = list(db.usage_log.aggregate(pipeline))
        # print( 'results: ', results)

        # Organize results by tenant_id
        tenants = collections.defaultdict(dict)
        for r in results:
            tenants[r["_id"]["tenant_id"]][r["_id"]["date"]] = r["count"]

        # Ensure all 7 days are present for each tenant
        tenants_with_all_days = {}
        for tenant_id, date_counts in tenants.items():
            tenants_with_all_days[tenant_id] = [
                {"date": date, "count": date_counts.get(date, 0)}
                for date in past_7_days
            ]

        # Convert tenant_id to tenant_name
        results = {
            config.tenants.get(tenant_id, {}).get("name"): tenants_with_all_days[
                tenant_id
            ]
            for tenant_id in tenants_with_all_days
        }

        # Filter out tenants with "Test" in their name
        results = {key: value for key, value in results.items() if "Test" not in key}

        # print( 'results: ', results)
        return results

    @staticmethod
    def get_ranking(top, month, year):
        tenant_id = config.user_info_var.get()["tenant_id"]
        print("tenant_id", tenant_id)
        if not tenant_id:
            return {}

        # Get the current year and month
        if not year:
            current_year = datetime.now().year
            current_month = datetime.now().month
        else:
            current_year = year
            current_month = month + 1

        # Find the top 3 users with the highest 'count' for the current year and month
        top_users = (
            db.users_usage.find(
                {
                    "year": current_year,
                    "month": current_month,
                    "tenant_id": tenant_id,
                    # 'count': {'$gte': 4}
                }
            )
            .sort("count", -1)
            .limit(top)
        )

        # Iterate through the top users and fetch their first names from the 'user' collection
        top_users_with_names = []
        for user_usage in top_users:
            user_id = user_usage["user_id"]
            user = db.users.find_one({"_id": user_id})
            if (
                user
                and "Teste" not in user["name"]
                and not user.get("exclude_from_ranking", False)
            ):
                first_name = user["name"].split()[0]
                top_users_with_names.append(
                    {
                        "user_id": str(user_id),
                        "count": user_usage["count"],
                        "first_name": first_name
                        + " "
                        + user["name"].split()[-1][0:1].upper(),
                        # 'first_name': first_name,
                        "name": user["name"],
                    }
                )

        return {
            "ranking": top_users_with_names[:top],
            "month": current_month - 1,
            "year": current_year,
        }
