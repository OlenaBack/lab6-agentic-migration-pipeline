namespace PayrollMigration;

using System.Collections.Generic;

public sealed class ValueError : Exception
{
    public ValueError(string message) : base(message) { }
}

public sealed record Employee(
    int EmployeeCode,
    string Name,
    int BasicSalary
);

public static class PayrollCalculator
{
    public static Dictionary<string, int> CalculateSalary(Employee employee)
    {
        if (employee.BasicSalary < 0)
        {
            throw new ValueError("Basic salary cannot be negative.");
        }
        
        var providentFund = (int)(employee.BasicSalary * 0.22);
        var dearnessAllowance = (int)(employee.BasicSalary * 0.10);
        var housingAllowance = (int)(employee.BasicSalary * 0.40);
        const int otherDeductions = 50;

        var totalEarnings =
            employee.BasicSalary
            + dearnessAllowance
            + housingAllowance;

        var totalDeductions =
            providentFund
            + otherDeductions;

        var netPay =
            totalEarnings
            - totalDeductions;

        return new Dictionary<string, int>
        {
            ["employee_code"] = employee.EmployeeCode,
            ["basic_salary"] = employee.BasicSalary,
            ["dearness_allowance"] = dearnessAllowance,
            ["housing_allowance"] = housingAllowance,
            ["provident_fund"] = providentFund,
            ["other_deductions"] = otherDeductions,
            ["total_earnings"] = totalEarnings,
            ["total_deductions"] = totalDeductions,
            ["net_pay"] = netPay,
        };
    }
}