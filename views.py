from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from csdjango.sb import models, forms
# Create your views here.

def accounts_sum(accounts):
    return sum([a.balance() for a in accounts])

@login_required
def account_list(request):
    accounts = models.Account.objects.all()
    return render(request, "sb/account_list.html",
            {"accounts": accounts})

@login_required
def account_details(request, pk):
    dateform = forms.DateRangeFilter(request.GET)
    begin, end = dateform.get_range()
    account = get_object_or_404(models.Account, pk=pk)
    account.period_transactions = account.get_transactions(begin, end)
    account.period_dt_sum = account.dt_sum(begin, end)
    account.period_ct_sum = account.ct_sum(begin, end)
    account.period_balance = account.pretty_balance(begin, end)
    return render(request, "sb/account_detail.html", 
            {"account": account, 'dateform': dateform})

@login_required
def doc_list(request):
    from django.db.models import Min, Max
    docs = models.SourceDoc.objects.annotate(min_date=Min("transactions__date"))
    docs = docs.annotate(max_date=Max("transactions__date")).all()
    return render(request, "sb/doc_list.html", {"docs": docs})

@login_required
def doc_details(request, pk):
    doc = get_object_or_404(models.SourceDoc, pk=pk)
    return render(request, "sb/doc_detail.html", {"doc": doc})

@login_required
def trans_details(request, pk):
    trans = get_object_or_404(models.Transaction, pk=pk)
    return render(request, "sb/trans_detail.html", {"trans": trans})

@login_required
def trans_list(request):
    dateform = forms.DateRangeFilter(request.GET)
    begin, end = dateform.get_range()
    transactions = models.Transaction.objects.all()
    if begin is not None:
        transactions = transactions.filter(date__gte=begin)
    if end is not None:
        transactions = transactions.filter(date__lte=end)
    return render(request, "sb/trans_list.html",
            {"transactions": transactions, 'dateform': dateform})

@login_required
def trial_balance(request):
    dateform = forms.DateRangeFilter(request.GET)
    begin, end = dateform.get_range()
    def annotate(cat):
        accounts = list(models.Account.objects.filter(cat=cat).all())
        for a in accounts:
            a.period_dt_sum = a.dt_sum(begin, end)
            a.period_ct_sum = a.ct_sum(begin, end)
            a.period_balance = a.balance(begin, end)
        return accounts
    accountDict = {
            "account_groups": [ {'cat': cat[1], 'accounts': annotate(cat[0])}
                for cat in models.ACCOUNT_CATEGORIES],
            'dateform': dateform}
    return render(request, "sb/trial_balance.html", accountDict)

@login_required
def add_payslip(request):
    if not request.user.is_superuser:
        raise PermissionDenied("Only super-users can add payslips")
    if request.method == "GET":
        pform = forms.PaySlipForm()
        dform = forms.SourceDocForm()
        rforms = forms.ReimbursementFormSet()
    elif request.method == "POST":
        pform = forms.PaySlipForm(request.POST)
        dform = forms.SourceDocForm(request.POST, request.FILES)
        rforms = forms.ReimbursementFormSet(request.POST)
        if pform.is_valid() and dform.is_valid() and rforms.is_valid():
            #Read data
            sourceDoc = dform.save(commit=False)
            sourceDoc.recordedBy=request.user
            sourceDoc.save()
            pdata = pform.cleaned_data
            employee = pdata["employee"]
            date = pdata["date"]
            grossAmount = pdata["gross"]
            payeAmount = pdata["paye"]
            uifAmount = pdata.get("uif", None)
            bonusAmount = pdata.get("bonus", None)
            print(bonusAmount)

            salaries = models.Account.objects.get(name="Salaries")
            paye = models.Account.objects.get(name="PAYE")
            uif = models.Account.objects.get(name="UIF")
            sars = models.Account.objects.get(name="SARS")
            bonusses = models.Account.objects.get(name="Bonusses")
            #generate transactions
            if payeAmount:
                #Increace employee account with paye ammount
                models.Transaction(debitAccount=paye, creditAccount=employee,
                        amount=payeAmount, date=date, recordedBy=request.user,
                        sourceDocument=sourceDoc, comments="", isConfirmed = True).save()
                #Move paye amount to SARS
                models.Transaction(debitAccount=employee, creditAccount=sars,
                        amount=payeAmount, date=date, recordedBy=request.user,
                        sourceDocument=sourceDoc, comments="", isConfirmed = True).save()
            else:
                payeAmount = Decimal(0.0)
            if uifAmount:
                #Increace employee account with paye ammount
                models.Transaction(debitAccount=uif, creditAccount=employee,
                        amount=uifAmount, date=date, recordedBy=request.user,
                        sourceDocument=sourceDoc, comments="", isConfirmed = True).save()
                #Move paye amount to SARS
                models.Transaction(debitAccount=employee, creditAccount=sars,
                        amount=uifAmount, date=date, recordedBy=request.user,
                        sourceDocument=sourceDoc, comments="", isConfirmed = True).save()
            else:
                uifAmount = Decimal(0.0)
            #Increace employee account with nett salary
            nett = grossAmount - payeAmount - uifAmount
            models.Transaction(debitAccount=salaries, creditAccount=employee,
                    amount=nett, date=date, recordedBy=request.user,
                    sourceDocument=sourceDoc, comments="", isConfirmed = True).save()
            #Increace employee account with bonus amount
            if bonusAmount:
                models.Transaction(debitAccount=bonusses, creditAccount=employee,
                        amount=bonusAmount, date=date, recordedBy=request.user,
                        sourceDocument=sourceDoc, comments="", isConfirmed = True).save()
            for rform in rforms:
                models.Transaction(debitAccount=rform.cleaned_data['account'],
                        creditAccount=employee, amount=rform.cleaned_data['amount'],
                        date=date, recordedBy=request.user, sourceDocument=sourceDoc,
                        comments="", isConfirmed = True).save()
            return redirect(sourceDoc)
    return render(request, "sb/payslip_form.html", 
            {'pform': pform, 'dform': dform, 'rforms': rforms})
      
@login_required
def income_statement(request):
    salesIncomeAccounts = models.Account.objects.filter(name="sales").all()
    salesIncomeSum = - accounts_sum(salesIncomeAccounts)
    sales = {"name": "Normal income", "accounts": salesIncomeAccounts, "sum": salesIncomeSum}
    otherIncomeAccounts = models.Account.objects.exclude(name="Sales").filter(cat="income").all()
    otherIncomeSum = - accounts_sum(otherIncomeAccounts)
    other = {"name": "Other income", "accounts": otherIncomeAccounts, "sum": otherIncomeSum}
    expenseAccounts = models.Account.objects.filter(cat="expense").all()
    expenseSum = - accounts_sum(expenseAccounts)
    expenses = {"name": "Expenses", "accounts": expenseAccounts, "sum": expenseSum}
    totalSum = salesIncomeSum + otherIncomeSum + expenseSum
    return render(request, "sb/income_statement.html", {"cats":[sales, other, expenses], "net": totalSum})
