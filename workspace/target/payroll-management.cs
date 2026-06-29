namespace PayrollMigration;

public sealed record Employee(
    int EmployeeCode,
    string Name,
    int BasicSalary
);

public sealed record SalaryBreakdown(
    int EmployeeCode,
    int BasicSalary,
    int DearnessAllowance,
    int HousingAllowance,
    int ProvidentFund,
    int OtherDeductions,
    int TotalEarnings,
    int TotalDeductions,
    int NetPay
);

public static class PayrollCalculator
{
    public static SalaryBreakdown CalculateSalary(Employee employee)
    {
        ArgumentNullException.ThrowIfNull(employee);

        if (employee.BasicSalary < 0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(employee),
                "Basic salary cannot be negative."
            );
        }

        var providentFund = (int)(employee.BasicSalary * 0.22m);
        var dearnessAllowance = (int)(employee.BasicSalary * 0.10m);
        var housingAllowance = (int)(employee.BasicSalary * 0.40m);
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

        return new SalaryBreakdown(
            EmployeeCode: employee.EmployeeCode,
            BasicSalary: employee.BasicSalary,
            DearnessAllowance: dearnessAllowance,
            HousingAllowance: housingAllowance,
            ProvidentFund: providentFund,
            OtherDeductions: otherDeductions,
            TotalEarnings: totalEarnings,
            TotalDeductions: totalDeductions,
            NetPay: netPay
        );
    }
}