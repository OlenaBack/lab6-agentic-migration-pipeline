from dataclasses import dataclass


@dataclass(frozen=True)
class Employee:
    employee_code: int
    name: str
    basic_salary: int


def calculate_salary(employee: Employee) -> dict[str, int]:
    """Calculate the employee's salary breakdown."""

    if employee.basic_salary < 0:
        raise ValueError("Basic salary cannot be negative.")

    provident_fund = int(employee.basic_salary * 0.22)
    dearness_allowance = int(employee.basic_salary * 0.10)
    housing_allowance = int(employee.basic_salary * 0.40)
    other_deductions = 50

    total_earnings = (
        employee.basic_salary
        + dearness_allowance
        + housing_allowance
    )

    total_deductions = provident_fund + other_deductions
    net_pay = total_earnings - total_deductions

    return {
        "employee_code": employee.employee_code,
        "basic_salary": employee.basic_salary,
        "dearness_allowance": dearness_allowance,
        "housing_allowance": housing_allowance,
        "provident_fund": provident_fund,
        "other_deductions": other_deductions,
        "total_earnings": total_earnings,
        "total_deductions": total_deductions,
        "net_pay": net_pay,
    }