from flask import Blueprint, request, current_app, redirect, url_for, jsonify, flash, make_response, Response
from flask_login import login_user, login_required, logout_user, current_user
from flask.templating import render_template
from forms import *
from application import db
from models import CustomBilling, Account, Billing, LogQuery, Plans, Invoice, Children
import os
import codecs
import json
import random
import time
import tinys3
import boto
import boto.s3.connection
import uuid
import itertools
import csv
import StringIO
import collections
from google.cloud import bigquery
from werkzeug.exceptions import HTTPException
from helpers import *

tools_app = Blueprint("tools_app", __name__, template_folder="templates")

@tools_app.context_processor
def inject_dict_for_all_templates():

    if "token" in request.cookies:
        return dict(stored_token = request.cookies["token"])
    else:
        return {}

@tools_app.route("/tools/removecookies")
def removecookies():
    resp = make_response(redirect('/tools'))
    resp.set_cookie('token', expires=0)
    return resp

@tools_app.route("/tools/", methods=["GET"])
@login_required
def tools():
    return render_template('tools/index.html')

@tools_app.route("/tools/help/", methods=["GET"])
@login_required
def help():
    return render_template('tools/help.html')

@tools_app.route("/tools/bookmarklets/", methods=["GET"])
@login_required
def bookmarklets():
    return render_template('tools/bookmarklets.html')

@tools_app.route("/tools/dashboard/", methods=["GET"])
@tools_app.route("/tools/dashboard/<token>/", methods=["GET","POST"])
@login_required
def tokendashboard(token=None):

    tokenForm = SingleInput(request.form)

    if request.method == 'POST' and tokenForm.validate():
        token = tokenForm.term.data
    elif not token:
        return redirect('/tools/gettoken')


    # #rules = getRules(token)
    # sections = [k for k in rules.keys()]
    # sections = sorted(sections, key=lambda v: v.upper())

    # account info

    account = Account.query.get(token)
    children_query = Children.query.filter((Children.parent==token)|(Children.token==token))
    children = []
    parent = None
    for row in children_query:
        if token == row.parent:
            children.append(row.token)
        elif token == row.token:
            parent = row.parent

    resp = make_response(render_template('tools/tokendashboard.html',
        token=token,
        account=account,
        stored_token=token,
        children=children,
        parent = parent)
    )
    resp.set_cookie('token', token)
    return resp
    return render_template('tools/tokendashboard.html',token=token,account=account,children=children)

@tools_app.route("/tools/usage/")
@tools_app.route("/tools/usage/<token>/")
@login_required
def tokenusage(token=None):

    fromdate = request.args.get('from') if request.args.get('from') else None
    todate = request.args.get('to') if request.args.get('to') else None

    if not token:
        if 'token' in request.cookies:
            token = request.cookies['token']
        else:
            return redirect_url('/tools/dashboard')

    usage = getUsage(token,fromdate,todate)

    if usage:
        totals = [
            sum([day['calls'] for day in usage]),
            sum([day['proxyCalls'] for day in usage]),
            sum([day['giCalls'] for day in usage]),
            sum([day['searchResults'] for day in usage]),
            sum([day['dqlFacetCount'] for day in usage])
        ]
    else:
        totals = []
    
    user = Account.query.get(token)
    return render_template('tools/usage.html',token=token,usage=usage,totals=totals,fromdate=fromdate,todate=todate,user=user)

@tools_app.route("/tools/jobs/")
@tools_app.route("/tools/jobs/<token>/")
@login_required
def jobs(token=None):

    jobDelete = JobDelete(request.form)

    if not token:
        if 'token' in request.cookies:
            token = request.cookies['token']
        else:
            return redirect_url('/tools/dashboard')

    jobs = getJobs(token)
    try:
        crawls = sorted(jobs['crawls'], key=lambda k: k['jobCreationTimeUTC'], reverse=True)
    except:
        crawls = None
    try:
        bulks = sorted(jobs['bulks'], key=lambda k: k['jobCreationTimeUTC'], reverse=True)
    except:
        bulks = None
    allJobs = (crawls + bulks)
    try:
        allJobs = sorted(allJobs, key=lambda k: k['jobCreationTimeUTC'], reverse=True)
    except:
        allJobs = None

    user = Account.query.get(token)

    return render_template(
        'tools/jobs.html',
        token=token,
        crawls=crawls,
        bulks=bulks,
        allJobs=allJobs,
        jobDeleteForm=jobDelete,
        user=user,
    )

@tools_app.route("/tools/job/<jobType>/facets/", methods=["GET"])
@login_required
def jobfacets(jobType=None):
    qs = request.args
    try:
        token = qs['token']
        name = qs['name']
        facet = qs['field']

    except:
        return redirect('/tools')

    if facet in [
        'gbssSpiderTime',
        'gbssIndexTimeDurationMS',
        'gbssDownloadDurationMS',
        'gbssNumOutlinksOnPage'
    ]:
        facet_ranges = getFacetRanges(token,name,facet)
        facet_query = "gbfacetint:%s,%s" % (facet,facet_ranges)

    elif facet in [
        'gbssMatchingUrlFilter',
        'gbssDiffbotReplyMsg'
    ]:
        facet_query = "gbfacetstr:%s" % facet
    else:
        facet_query = "gbfacetint:%s" % facet

    facet_data = getFacetData(token,name,facet_query)


    return render_template(
        'tools/jobfacets.html',
        token=token,
        name=name,
        facet_data=facet_data,
        jobType=jobType
        )

@tools_app.route("/tools/out/")
def outlink():
    qs = request.args
    try:
        url = qs['url']
    except:
        return redirect('/tools')
    return redirect(url)

@tools_app.route("/tools/job/<jobType>/", methods=["GET"])
@login_required
def jobdetails(jobType=None):

    qs = request.args
    try:
        token = qs['token']
        name = qs['name']
    except:
        return redirect('/tools')

    if not jobType:
        return redirect('/tools')

    job = getJob(token,name,jobType)

    if jobType == "crawl":
        seedHosts = [getHost(i) for i in job['seeds'].split(' ')]
        seedHosts = list(set(seedHosts))
    else:
        seedHosts = []

    jobsorted = collections.OrderedDict(sorted(job.items()))

    gigablast_url = get_gigablast_url(token, name)
    return render_template(
        'tools/jobdetail.html',
        token=token,
        name=name,
        jobType=jobType,
        job=job,
        seedHosts=seedHosts,
        jobJson=json.dumps(jobsorted,indent=3),
        gigablast_url=gigablast_url
        )

@tools_app.route("/tools/job/copy/", methods=["POST"])
@login_required
def copyJob():

    newJobData = request.get_data()
    newJobJson = json.loads(newJobData)
    newJobJson['notifyEmail'] = ""
    newJobJson['notifyWebhook'] = ""
    newHeaders = []
    for k,v in newJobJson['customHeaders'].items():
        newHeaders.append("%s:%s" % (k,v))
    newJobJson['customHeaders'] = newHeaders

    print json.dumps(newJobJson,indent=2)

    r = requests.post('http://api.diffbot.com/v3/crawl?pause=1',data=newJobJson)

    try:
        j = r.json()
        print j
        if "Successfully added" in j["response"]:
            message = {"message":"Successfully duplicated job."}
        else:
            message = j
    except:
        message = {"message":"Problem copying job."}

    return json.dumps(message)

@tools_app.route("/tools/jobdelete/", methods=["GET","POST"])
@login_required
def deleteJobs():
    jobDelete = JobDelete(request.form)
    preview = request.args.get('preview',False)

    if request.method == 'POST' and jobDelete.validate():

        preview = request.args.get('preview',False)

        # get list of jobs
        list_of_jobs = []
        if len(jobDelete.token.data) > 0:
            jobs = getJobs(jobDelete.token.data,namesOnly=True)
            for k,v in jobs.items():
                for job in v:
                    list_of_jobs.append(job)
        elif len(jobDelete.jobs.data) > 0:
            list_of_jobs = jobDelete.jobs.data.replace('\r','')
            list_of_jobs = list_of_jobs.split('\n')
        else:
            flash("Please enter a token or list of jobs to delete")
        list_of_jobs = [[i.split("-")[0],"-".join(i.split('-')[1:])] for i in list_of_jobs]
        return render_template(
            'tools/jobBulkDelete.html',
            jobDeleteForm=jobDelete,
            jobsToDelete=list_of_jobs,
            preview=preview
        )

    elif request.method == 'POST':
        flash("Error finding jobs to delete")

    return render_template(
        'tools/jobBulkDelete.html',
        jobDeleteForm=jobDelete
    )


@tools_app.route("/tools/account/change/<token>", methods=["POST","GET"])
@login_required
def accountChange(token=None):

    if "test" in request.args:
        STRIPE_KEY = current_app.config['TEST_STRIPE_API_KEY']
    else:
        STRIPE_KEY = current_app.config['STRIPE_API_KEY']

    # get user details
    user = Account.query.get(token)
    stripe_data = Billing.query.filter_by(token=token).first()
    db.session.close()

    try:
        stripe_cid = stripe_data.stripe_cid
    except:
        return redirect('/tools/account')

    if not user:
        return redirect('/tools/account')

    # get current stripe plan
    try:
        stripe_customer = getStripeCustomer(stripe_cid,STRIPE_KEY)
        current_stripe_plan = stripe_customer['subscriptions']['data'][0]['plan']['name']
    except:
        flash("Error: No current billing plan for this account")
        return redirect('tools/account/%s' % token)

    if not current_stripe_plan:
        flash("Error: No current billing plan for this account")
        return redirect('tools/account/%s' % token)

    # get available plans // upgrade and downgrade
    paid_plans = Plans.query.filter(Plans.price_month > 0)
    db.session.close()

    accountChangeForm = AccountChange(request.form)
    accountChangeForm.plan.choices = [(plan.name,"%s ($%d/month)" % (plan.name,plan.price_month/100)) for plan in paid_plans]

    if request.method == 'POST' and accountChangeForm.validate():

        new_plan = accountChangeForm.plan.data
        retroactive = accountChangeForm.retroactive.data
        # compare difference

        if not retroactive:
            # change it at the end of this cycle
            # only change it in stripe for now

            sub = updateStripeSubscription(stripe_cid,STRIPE_KEY,new_plan=new_plan)
            if not sub:
                flash("Error updating subscription")
                return render_template('tools/accountChange.html',user=user, accountChangeForm=accountChangeForm,token=token,plans=paid_plans)
            else:
                flash("Updated subscription")
                return redirect('tools/account/change/%s' % token)

        else:

            for plan in paid_plans:
                if plan.name.lower() == current_stripe_plan.lower():
                    old_amount = plan.price_month
                if plan.name.lower() == new_plan.lower():
                    new_amount = plan.price_month
                    new_price_month = plan.price_month
                    new_price_overage = plan.price_overage
                    new_calls_included = plan.calls_included

            # charge the amount immediately

            try:
                immediate_charge = new_amount - old_amount
            except:
                flash("Error calculating immediate charge.")
                return render_template('tools/accountChange.html',user=user, accountChangeForm=accountChangeForm,token=token,plans=paid_plans)

            if immediate_charge > 0:
                charge = stripeCharge(stripe_cid,STRIPE_KEY,immediate_charge)

            elif immediate_charge < 0:
                # it's a downgrade, adjust the plans everywhere
                # even though the admin indicated retroactively apply it

                # update plan in MySQL
                user = Account.query.get(token)
                user.plan = new_plan

                sub = updateStripeSubscription(stripe_cid,STRIPE_KEY,new_plan=new_plan)

                try:
                    db.session.commit()
                    db.session.close()
                except:
                    flash("Error saving updated plan")
                    db.session.rollback()
                    db.session.close()

                flash("Successfully updated plan")

                return redirect('tools/account/change/%s' % token)

            if charge:
                print "charge successful"
                # update subscription
                sub = updateStripeSubscription(stripe_cid,STRIPE_KEY,new_plan=new_plan)

                # invoice data:
                invoice_data = {
                    'name':user.name,
                    'date': datetime.datetime.now().strftime("%b %d, %Y"),
                    'last4': charge['source']['last4'],
                    'exp_month': charge['source']['exp_month'],
                    'exp_year': charge['source']['exp_year'],
                    'amount': immediate_charge,
                    'plan_name': new_plan.capitalize(),
                    'price_month': new_price_month,
                    'price_overage': new_price_overage,
                    'calls_included': new_calls_included
                }

                # send an email invoice
                email = sendInvoice(current_app.config['MANDRILL_KEY'],user.email,invoice_data)
                if not email:
                    flash("Error sending invoice")

                # update plan in MySQL
                user = Account.query.get(token)
                user.plan = new_plan

                # add a DB invoice
                invoice = Invoice(
                    token = token,
                    date = datetime.datetime.now().strftime("%Y-%m-%d 00:00:00"),
                    plan = new_plan,
                    calls = 0,
                    total = immediate_charge,
                    status = 0
                )
                db.session.add(invoice)
                try:
                    db.session.commit()
                    invoice_id = invoice.id
                    db.session.close()
                except:
                    flash("Error saving invoice")
                    db.session.rollback()
                    db.session.close()

                return redirect('tools/account/change/%s' % token)

            else:
                flash("Error charging card.")
                return render_template('tools/accountChange.html',user=user, accountChangeForm=accountChangeForm,token=token,plans=paid_plans)


    elif request.method=='POST' and not accountChangeForm.validate():
        print accountChangeForm.plan.data
        for field, errors in accountChangeForm.errors.iteritems():
            print field
            print errors

    elif request.method == "GET":

        return render_template(
            'tools/accountChange.html',
            user=user,
            accountChangeForm=accountChangeForm,
            token=token,
            plans=paid_plans,
            current_stripe_plan=current_stripe_plan
        )




    # retroactive or not
    # change the plan in Stripe
    # update MySQL

@tools_app.route("/tools/discount/<token>/", methods=["GET","POST"])
@login_required
def accountDiscount(token=None):

    if not token:
        return redirect('tools/account/')

    if "test" in request.args:
        STRIPE_KEY = current_app.config['TEST_STRIPE_API_KEY']
        flash("Using Stripe test key")
    else:
        STRIPE_KEY = current_app.config['STRIPE_API_KEY']

    discountForm = Discount(request.form)

    try:
        stripe_data = Billing.query.filter_by(token=token).first()
        stripe_cid = stripe_data.stripe_cid
    except:
        db.session.rollback()
        db.session.close()
        stripe_cid = None

    if not stripe_cid:
        flash("Error: No current billing plan for this account")
        return redirect('tools/account/%s' % token)

    try:
        stripe_customer_data = getStripeCustomer(stripe_cid,STRIPE_KEY)
    except:
        flash("Error: Could not retrieve account information")
        return redirect('tools/account/%s' % token)

    try:
        current_stripe_plan = stripe_customer_data['subscriptions']['data'][0]['plan']['name']
    except:
        current_stripe_plan = None
        flash("Error: Customer does not have an active billing plan.")
        return redirect('tools/account/%s' % token)

    # if already a discount applied, redirect.
    try:
        current_discount = stripe_customer_data['discount']
    except:
        current_discount = None
    if current_discount:
        flash("Error: Customer already has a discount applied")
        return redirect('tools/account/%s' % token)

    if request.method == "GET":

        return render_template(
            'tools/accountDiscount.html',
            discountForm=discountForm,
            token=token,
            current_stripe_plan=current_stripe_plan
        )

    elif request.method == "POST" and discountForm.validate():
        coupon = discountForm.coupon.data
        length = int(discountForm.length.data)
        retroactive = discountForm.retroactive.data
        immediate_credit = None
        coupon_code = "api%s_%d" % (coupon,length)

        try:
            user = Account.query.get(token)
        except:
            db.session.rollback()
            db.session.close()
            flash("There was an error accessing the database.")
            return redirect('/tools/account')

        if user:
            user_plan = Plans.query.filter(Plans.name == user.plan).first()
            current_plan_amount = user_plan.price_month

        # get current plan amount
        if retroactive:
            coupon_code = "api%s_%d" % (coupon,(length-1))
            if "percent" in coupon:
                percentage = (1-float(coupon.replace('percent',''))/100.0)
                immediate_credit = int((current_plan_amount * percentage))
            else:
                immediate_credit = int(coupon)

        # apply the coupon
        sub = updateStripeCustomer(stripe_cid,STRIPE_KEY,coupon=coupon_code)
        if not sub:
            flash("Error adding discount. No changes made.")
            return redirect('tools/account/%s' % token)
        else:
            flash("Applied coupon %s" % coupon_code)

        if immediate_credit:
            print "Immediate credit of: %d" % immediate_credit
            charge = stripeCharge(stripe_cid,STRIPE_KEY,(-1 * immediate_credit))
            if charge:
                flash("Credit applied to next invoice: $%s" % '{:,.2f}'.format(immediate_credit/100.0))
            else:
                flash("Error retroactively crediting account")

        return redirect('tools/account/%s' % token)

        # if immediate_credit:
        #     stripe.InvoiceItem.create(
        #       customer ="%s" % customer_id,
        #       amount = immediate_discount,
        #       currency = "usd",
        #       description = "Authorized credit for discount"
        #     )

        # apply coupon to the subscription


@tools_app.route("/tools/account", methods=["GET"])
@tools_app.route("/tools/account/<token>", methods=["GET","POST"])
@login_required
def account(token=None):

    if "test" in request.args:
        STRIPE_KEY = current_app.config['TEST_STRIPE_API_KEY']
    else:
        STRIPE_KEY = current_app.config['STRIPE_API_KEY']

    accountForm = Accounts(request.form)

    # get stripe data if it exists
    try:
        stripe_data = Billing.query.filter_by(token=token).first()
        stripe_cid = stripe_data.stripe_cid
    except:
        db.session.rollback()
        db.session.close()
        stripe_cid = None

    if stripe_cid:
        stripe_customer_data = getStripeCustomer(stripe_cid,STRIPE_KEY)
        invoices = Invoice.query.filter(Invoice.token == token).order_by("date")

    else:
        stripe_customer_data = None
        invoices = None

    try:
        current_stripe_plan = stripe_customer_data['subscriptions']['data'][0]['plan']['name']
    except:
        current_stripe_plan = None

    try:
        current_discount = stripe_customer_data['discount']
    except:
        current_discount = None

    if request.method == 'POST' and not accountForm.validate():
        print accountForm.errors

    if request.method == 'POST' and accountForm.validate():
        try:
            user = Account.query.get(token)
        except:
            db.session.rollback()
            db.session.close()
            flash("There was an error accessing the database.")
            return redirect('/tools/account')

        user.reason = accountForm.reason.data
        user.blocked = accountForm.blocked.data
        user.email = accountForm.email.data
        user.created = accountForm.created.data
        user.name = accountForm.name.data

        if accountForm.blocked.data == "1":

            if accountForm.cancelStripe.data == "2":
                #immediate cancel
                try:
                    cancelChildren(token)
                except:
                    flash("Was not able to cancel child tokens.")

                if stripe_customer_data and stripe_cid:
                    stripe_status = cancelStripe(stripe_cid,STRIPE_KEY,immediately=True)
                    if stripe_status:
                        flash("Immediate cancellation successful.")
                    else:
                        flash("Error cancelling Stripe or there was no Stripe plan to cancel.")
                else:
                    flash("No billing to cancel or another error occurred.")

            elif accountForm.cancelStripe.data == "1":
                #cancel Stripe at end of period
                if stripe_customer_data and stripe_cid:
                    user.blocked = "0"
                    stripe_status = cancelStripe(stripe_cid,STRIPE_KEY)
                    if stripe_status:
                        flash("Cancellation successfully scheduled at end of billing period")
                    else:
                        flash("Cancellation was NOT successfully scheduled")
                else:
                    flash("No billing to cancel or another error occurred.")
        try:
            db.session.commit()
            db.session.close()
        except Exception as e:
            flash("There was an error updating the user's status in the database.")
            db.session.rollback()
            db.session.close()

        user = Account.query.get(token)
        db.session.close()

    else:
        if not token:
            if 'token' in request.cookies:
                token = request.cookies['token']
            else:
                return redirect_url('/tools/dashboard')
        user = Account.query.get(token)
        db.session.close()

    # get current stripe status


    return render_template(
        'tools/account.html',
        user=user,
        accountForm=accountForm,
        token=token,
        stripe_customer_data=stripe_customer_data,
        current_stripe_plan=current_stripe_plan,
        current_discount=current_discount,
        invoices=invoices
        )

# @tools_app.route("/tools/upgrade", methods=["GET"])
# @login_required
# def custombilling():

@tools_app.route("/tools/custombilling", methods=["GET"])
@login_required
def custombilling():

    today = datetime.datetime.today()
    last90 = (today + datetime.timedelta(-90)).strftime("%Y-%m-01")

    qs = request.args
    if 'showall' in qs:
        invoices = CustomBilling.query.order_by("name").order_by("start desc").all()
    else:
        invoices = CustomBilling.query.filter(CustomBilling.end >= last90).order_by("name").order_by("start desc")
    db.session.close()
    return render_template('tools/custombilling.html',invoices=invoices,today=datetime.date.today())

@tools_app.route("/tools/custombilling/<dbid>", methods=["GET","POST"])
@login_required
def custombilling_add(dbid):
    billingForm = Invoices(request.form)
    today = datetime.datetime.today().strftime("%Y-%m-01")

    disabled = {}

    if request.method == "POST" and billingForm.validate():

        invoice_id = None

        if billingForm.id.data != "":
            # it's an edit
            invoice = CustomBilling.query.get(billingForm.id.data)
            invoice.cancel = billingForm.cancel.data
            invoice.token = billingForm.token.data
            invoice.account_manager = billingForm.account_manager.data
            invoice.email = billingForm.email.data


        else:
            # it's brand new, either a renewal or totally new one
            if billingForm.cm_extid.data == "":
                cm_extid = billingForm.name.data.replace(' ','').lower()
            else:
                cm_extid = billingForm.cm_extid.data
            invoice = CustomBilling(
                name = billingForm.name.data,
                amount = billingForm.amount.data,
                type = billingForm.type.data,
                interval = billingForm.interval.data,
                length = billingForm.length.data,
                start = billingForm.start.data,
                end = billingForm.end.data,
                cancel = billingForm.cancel.data,
                note = billingForm.note.data,
                cm_extid = cm_extid,
                cm_uuid = billingForm.cm_uuid.data,
                cm_subid=billingForm.cm_subid.data,
                token=billingForm.token.data,
                account_manager=billingForm.account_manager.data,
                email=billingForm.email.data,
            )
            db.session.add(invoice)
        try:
            db.session.commit()
            invoice_id = invoice.id
            db.session.close()
        except Exception as e:
            print "Error: %s" % e
            db.session.rollback()
        url = "/tools/custombilling/%s" % invoice_id
        return redirect(url)

    else:
        renewal_status = False
        if dbid == "new":
            disable_status = False
            invoice = {}
            qs = request.args
            if 'from' in qs:
                invoice = CustomBilling.query.get(qs['from'])
                disable_status = True
                renewal_status = True
        else:
            disable_status = True
            invoice = CustomBilling.query.get(dbid)
            request_type = "edit"

        return render_template('tools/custombilling_add.html',
            invoice=invoice,billingForm=billingForm,disable_status=disable_status,renewal=renewal_status,dbid=dbid
        )

        print billingForm.errors
        db.session.close()
        return render_template('tools/custombilling_add.html',invoice=invoice,billingForm=billingForm)

@tools_app.route("/tools/customplans", methods=["GET"])
@tools_app.route("/tools/customplans/<token>", methods=["GET","POST"])
@login_required
def customplans(token=None):

    planForm = CustomPlans(request.form)
    db = Database()

    if request.method == 'POST' and planForm.validate() and token:
        notesToUpdate = db.call("SELECT notes from api_custom WHERE token = %s" , token)
        newnotes = planForm.notes.data
        oldnotes = notesToUpdate[0][0]
        if len(oldnotes) > 0:
            finalnotes = oldnotes + '||' + newnotes
        else:
            finalnotes = newnotes
        finalnotes = finalnotes.replace("'","''").replace('"','""')
        update = db.insert("UPDATE api_custom SET notes=%s WHERE token = %s LIMIT 1" , finalnotes,token)

    users = db.call('SELECT api.token,api.plan,api.email,api.name,api.blocked,api_custom.action,api_custom.notes,api_custom.end FROM api INNER JOIN api_custom on api.token = api_custom.token and api.blocked != 1 ORDER BY api_custom.end')
    finalusers = []
    tokenData = None

    for u in users:
        newrow = [u[0],u[1],u[2],u[3].decode('latin-1'),u[4],u[5],u[6].replace('||','<br /><br />'),u[7].strftime("%Y-%m-%d")]
        finalusers.append(newrow)
        if u[0] == token:
            tokenData = newrow

    return render_template('tools/customplans.html', planForm=planForm,users=finalusers, tokenData=tokenData)

@tools_app.route("/tools/xevaluate", methods=["POST","GET"])
@tools_app.route("/tools/xevaluate/<action>", methods=["POST"])
def customrulesxeval(action=None):

    if request.method == "POST":

        rule = request.form.get('rule')
        j = json.loads(rule)

        if "xForwardHeaders" in j and "X-Evaluate" in j['xForwardHeaders']:
            xeval = j['xForwardHeaders']['X-Evaluate']
            xeval = beautify(xeval)
        else:
            xeval = None

    else:
        j = {}
        xeval = None

    return render_template('tools/customrules_xeval.html', json=j, xeval=xeval, rule=json.dumps(j))

@tools_app.route("/tools/customrules", methods=["GET","POST"])
@tools_app.route("/tools/customrules/<token>", methods=["GET"])
@tools_app.route("/tools/customrules/<token>/<action>", methods=["POST"])
@login_required
def customrules(token=None,action=None):

    tokenForm = SingleInput(request.form)

    if not token:
        if 'token' in request.cookies:
            token = request.cookies['token']
        else:
            token = None

    if request.method == 'GET' and not token and not action:
        return render_template('tools/customrules.html', tokenForm=tokenForm)

    if request.method == 'POST' and tokenForm.validate() and tokenForm.term.data:
        return redirect('/tools/customrules/%s' % tokenForm.term.data)

    if token:
        rules = getRules(token)
        sections = [k for k in rules.keys()]
        sections = sorted(sections, key=lambda v: v.upper())

    if request.method == 'POST' and action:
        if action == "delete":
            r = updateRules(token,request.json,delete=True)
            return json.dumps({"success":"Success"})

        elif action == "update":
            r = updateRules(token,request.json)
            return json.dumps(r)

        else:
            return json.dumps({"error":"incorrect POST mechanism"})
    
    user = Account.query.get(token)

    return render_template('tools/customrules.html', rules=rules, sections=sections, token=token, user=user)

@tools_app.route("/tools/proxies/", methods=["GET","POST"])
@login_required
def proxies():

    if request.method == 'GET':
        proxies = manageProxies()
        return render_template('tools/proxies.html',proxies=proxies)

    if request.method == 'POST':
        r = manageProxies(request.json)
        return json.dumps({"success":"rules should be updated"})

@tools_app.route("/tools/testdrive/", methods=["GET","POST"])
@tools_app.route("/tools/testproxy/", methods=["GET"])
@login_required
def testdrive():

    tdForm = TestDrive(request.form)
    if request.method == 'GET':
        proxies = manageProxies()
        proxySet = [(k,k) for k in proxies.keys()]
        proxySet.sort()
        proxySet.insert(0,("None","None"))
        tdForm.proxySet.choices = proxySet

        qs = request.args
        url = qs['url'] if 'url' in qs else ""
        token = qs['token'] if 'token' in qs else ""

        return render_template(
            'tools/testdrive.html',
            proxies=proxies,
            tdForm=tdForm,
            url=url,
            token=token
        )

    if request.method == 'POST':
        url = tdForm.url.data
        proxySet = tdForm.proxySet.data
        manualProxy = tdForm.manualProxy.data
        api = tdForm.api.data
        token = tdForm.token.data
        headers = tdForm.headers.data
        call_arguments = tdForm.otherArgs.data
        xeval = tdForm.xeval.data

        token = "diffbotlabstoken" if not token else token

        headers_dict = {}
        if headers:
            headers = headers.split('\n')
            for row in headers:
                kv = row.split(':')
                headers_dict["X-Forward-%s" % kv[0]] = ":".join(kv[1:]).strip()

        if xeval and len(xeval) > 5:
            headers_dict['X-Forward-X-Evaluate'] = xeval
            headers_dict['X-Evaluate'] = xeval


        if not call_arguments:
            call_arguments = ""

        if manualProxy:
            selectedProxy = manualProxy.split('@')
            proxystring = "&proxy=%s&proxyAuth=%s" % (selectedProxy[1],selectedProxy[0])
            call_arguments += proxystring
        elif proxySet != "None":
            proxies = manageProxies()
            selected = random.choice(proxies[proxySet]).split("@")
            proxystring = "&proxy=%s&proxyAuth=%s" % (selected[1],selected[0])
            call_arguments += proxystring

        if "render" in api:
            redirect_url = rendererUrl(url,call_arguments)
            r = requests.get(redirect_url,headers=headers_dict)
            return render_template('/tools/preview.html', html=r.text, url=redirect_url)
        elif "td_" in api:
            redirect_url = "http://www.diffbot.com/testdrive/?api=%s?stats&admin&token=%s&url=%s%s" % (
                api.replace("td_",""),
                token,
                encodeUrl(url),
                call_arguments
                )
            return redirect(redirect_url)
        elif "api_dom" in api:
            print "api_dom"
            redirect_url = "http://api.diffbot.com/v3/article?fields=dom&token=%s&url=%s%s" % (
                token,
                encodeUrl(url),
                call_arguments
            )
            r = requests.get(redirect_url,headers=headers_dict)
            return render_template('/tools/preview.html',
                html=r.json()['objects'][0]['dom'],
                url=redirect_url
                )
        else:
            redirect_url = "http://api.diffbot.com/v3/%s?stats&admin&token=%s&url=%s%s" % (
                api,
                token,
                encodeUrl(url),
                call_arguments
                )
            r = requests.get(redirect_url,headers=headers_dict)
            return render_template('/tools/preview.html', jsondata=r.json())

        proxySet = [(k,k) for k in proxies.keys()]
        proxySet.sort()
        proxySet.insert(0,("None","None"))
        tdForm.proxySet.choices = proxySet

        return render_template('tools/testdrive.html',proxies=proxies, tdForm=tdForm)

@tools_app.route("/tools/multiple", methods=["GET","POST"])
@login_required
def multiple():

    urlForm = URL(request.form)

    if request.method == 'POST' and urlForm.validate():
        url = urlForm.url.data
        url = encodeUrl(url)
        api = urlForm.api.data
        num = urlForm.num.data
        if urlForm.token.data:
            token = urlForm.token.data
        else:
            token = 'johnnorules'
        params = urlForm.params.data
        return render_template('tools/multiple.html', urlForm=urlForm, url=url, api=api, num=num, token=token,params=params)

    return render_template('tools/multiple.html', urlForm=urlForm)

@tools_app.route("/tools/debugger", methods=["GET","POST"])
@login_required
def debugger():

    urlForm = URLDebug(request.form)

    if request.method == 'POST' and urlForm.validate():
        url = urlForm.url.data
        url = encodeUrl(url)
        api = urlForm.api.data
        if urlForm.token.data:
            token = urlForm.token.data
        else:
            token = 'johnnorules'
        return render_template('tools/debugger.html', urlForm=urlForm, url=url, api=api, token=token)
    return render_template('tools/debugger.html', urlForm=urlForm)

@tools_app.route("/tools/allips", methods=["GET","POST"])
def allips():
    # return a list of the IPs to the page; page iterates through them
    pass

@tools_app.route("/tools/allrenderers", methods=["GET","POST"])
def allrenderers():
    # return a list of the IPs to the page; page iterates through them
    pass

@tools_app.route("/tools/renderer", methods=["GET","POST"])
@login_required
def renderer():

    urlForm = ViewInRenderer(request.form)

    qs = request.args
    url = qs['url'] if 'url' in qs else None
    args = qs['args'] if 'args' in qs else None

    if request.method == 'POST' and urlForm.validate():
        url = urlForm.url.data
        args = urlForm.args.data
        redirect_url = rendererUrl(url,args)
        return redirect(redirect_url)
    elif url:
        redirect_url = rendererUrl(url,args)
        return redirect(redirect_url)
    else:
        return render_template('tools/renderer.html', urlForm=urlForm)

@tools_app.route("/tools/rendererView", methods=["GET","POST"])
@login_required
def rendererView():
    xeval = request.form.get('xeval')
    xeval = beautify(xeval,encode=True,sq=True)
    headers = {"X-Forward-X-Evaluate":xeval,"X-Evaluate":xeval}

    rule = request.form.get('rule')
    j = json.loads(rule)
    url = request.form.get('testUrl')
    redirect_url = rendererUrl(url)
    r = requests.get(redirect_url,headers=headers)
    return render_template('/tools/preview.html', html=r.text, xeval=xeval)

@tools_app.route("/tools/gettoken", methods=["GET","POST"])
@tools_app.route("/tools/gettoken/<term>", methods=["GET","POST"])
@login_required
def gettoken(term=None):

    db = Database()
    tokenForm = SingleInput(request.form)
    if request.method == 'POST' and tokenForm.validate():
        term = tokenForm.term.data
    elif 'term' in request.args:
        term = request.args['term']
    if term:
        users = db.call("SELECT api.token,api.name,api.email,api.plan,api.blocked,api_children.parent as parent_token from api LEFT JOIN api_children ON api.token = api_children.token where api.email LIKE %s OR api.token = %s OR api.name LIKE %s OR api.reason LIKE %s ORDER BY api.blocked DESC, api_children.parent ASC", '%'+term+'%',term,'%'+term+'%','%'+term+'%')
        scrubbedusers = {
            "active":[],
            "inactive":[]
        }

        for u in users:
            newrow = [u[0],u[1].decode('utf-8','ignore'), u[2].decode('utf-8','ignore'),u[3],u[4],u[5]]
            if newrow[4] == 1 or newrow[3] == "free":
                scrubbedusers['inactive'].append(newrow)
            else:
                scrubbedusers['active'].append(newrow)
        return render_template('tools/gettoken.html', tokenForm=tokenForm, users=scrubbedusers)
    else:
        return render_template('tools/gettoken.html', tokenForm=tokenForm)

@tools_app.route("/tools/replacetoken", methods=['GET','POST'])
@login_required
def replacetoken():
    '''replace a token'''

    qs = request.args
    old_token = qs['old'] if 'old' in qs else None
    new_token = qs['new'] if 'new' in qs else None

    tokenForm = ReplaceToken(request.form)

    if request.method == "GET":
        tokenForm.old_token.data = old_token
        tokenForm.new_token.data = new_token

    elif request.method == 'POST' and tokenForm.validate():
        new_token = tokenForm.new_token.data
        old_token = tokenForm.old_token.data

        # make sure the token being replaced isn't a child
        child_status = Children.query.filter(Children.token==old_token)
        if child_status.count() > 0:
            flash("Please try again. Only primary tokens can be replaced or have children.")
            return render_template('tools/replacetoken.html',tokenForm=tokenForm)

        # make the various DB updates
        db = Database()

        calls = [
            ("UPDATE invoice SET token = %s WHERE token = %s"       , (new_token,old_token)),
            ("UPDATE credit_card SET token = %s WHERE token = %s"   , (new_token,old_token)),
            ("UPDATE api_analytics SET token = %s WHERE token = %s" , (new_token,old_token)),
            ("UPDATE api_children SET parent = %s WHERE parent = %s"  , (new_token,old_token)),
            ("UPDATE api SET blocked='1' WHERE token = %s"          , (old_token,))
        ]
        # first, check if the old token is a replacement itself

        prior_replacement = db.call("SELECT * from api_children WHERE token = %s AND type = '1'" , old_token)
        if len(prior_replacement) > 0:
            insert_call = ("INSERT INTO api_children (token,parent,type) VALUES (%s, %s, '1')" , (new_token,prior_replacement[0][1]))
            calls.append(insert_call)
        else:
            calls.append(("INSERT INTO api_children (token,parent,type) VALUES (%s, %s, '1')" , (new_token, old_token)))
        for (call,args) in calls:
            db.insert(call, *args)
 
        return render_template('tools/replacetoken.html',tokenForm=tokenForm, success=True)

    return render_template('tools/replacetoken.html',tokenForm=tokenForm)


@tools_app.route("/tools/childtokens", methods=["GET","POST"])
@login_required
def childtokens():
    # generate child tokens

    tokenForm = ChildTokens(request.form)

    if request.method == 'POST' and tokenForm.validate():
        parent = tokenForm.parent.data
        num = int(tokenForm.num.data)
        tokenType = int(tokenForm.tokenType.data)

        # make sure you're dealing with a parent token
        child_status = Children.query.filter(Children.token==parent)
        if child_status.count() > 0:
            flash("Please try again. Only primary tokens can be replaced or have children.")
            return render_template('tools/childtokens.html',tokenForm=tokenForm)

        if tokenType == 1:
            # it's a replacement token
            # only generate one
            tokens = genToken(1)
        else:
            tokens = genToken(num)

        db = Database()

        # get parent data
        p = db.call("SELECT token,name,email,plan FROM api WHERE token = %s LIMIT 1" , parent)
        parentName = p[0][1]
        parentEmail = p[0][2]
        parentPlan = p[0][3]

        for token in tokens:

            i1 = db.insert("INSERT INTO api (token,name,email,plan) VALUES (%s,%s,%s,%s)" , token,parentName,parentEmail,parentPlan)
            # insert children into api_children
            if tokenType == 0:
                i1 = db.insert("INSERT INTO api_children (token,parent,type) VALUES (%s,%s,%s)" , token,parent,tokenType)

        return render_template('tools/childtokens.html',tokenForm=tokenForm,tokens=tokens,tokenType=tokenType)

    return render_template('tools/childtokens.html',tokenForm=tokenForm)

@tools_app.route("/tools/crawlbot_usage/", methods=["GET"])
@login_required
def crawlbot_usage(bucket="crawlbot"):
    url = request.args.get('url')
    if not url:
        return redirect('/tools/backup/crawlbot_usage')
    date = url.split('/')[-1].split('.txt')[0]
    data = fetchbackup(url,text=False)
    return render_template('tools/crawlbot_usage.html', data=data,date=date)

@tools_app.route("/tools/backup/<path:bucket>", methods=["GET"])
@login_required
def backup(bucket="crawlbot"):

    bucket = bucket.rstrip('/') + "/"

    # connect to S3
    key = 'AKIAJ7EESYFLFLWA7HIA'
    skey = 'aGflGMbo4Xh5b0zYvkEfhjpLtbEVB1Di66eL88om'
    conn = boto.s3.connect_to_region('us-west-1',
       aws_access_key_id=key,
       aws_secret_access_key=skey,
       is_secure=False,
       calling_format = boto.s3.connection.OrdinaryCallingFormat()
    )
    mybucket = conn.get_bucket("backup.diffbot.com")
    s3keys = mybucket.list(bucket,"/")

    if "crawlbot_usage" in bucket:
        final_level = True
    elif "/20" not in bucket: # you're not at the final level
        final_level = False
        s3keys = sorted(s3keys, key=lambda k: k.name,reverse=True)
    else:
        final_level = True
    return render_template('tools/backup.html',s3keys=s3keys, bucket=bucket, final_level=final_level)

@tools_app.route("/tools/backup/fetch/", methods=["GET","POST"])
@login_required
def backupfetch():
    url = request.args.get('url')
    fetchdata = fetchbackup(url)
    tokenForm = TokenCopy(request.form)

    if request.method == 'POST' and tokenForm.validate():

        token_to_update = tokenForm.token2.data
        success = True
        if 'errorCode' in fetchdata:
            success = False

        if success:

            restore_type = request.args.get('type',"custom")
            if restore_type == "crawl":
                current_jobs = getJobs(token_to_update)
                prior_jobs = fetchbackup(url,text=False)

                if type(prior_jobs) == dict:
                    prior_jobs = [prior_jobs]

                for job in prior_jobs:
                    job_type = job['type']
                    if job['name'] in current_jobs['bulks'] or job['name'] in current_jobs['crawls']:
                        pass
                    if job['type'] == "bulk":
                        pass
                    else:
                        job['pause'] = 1
                        job['token'] = token_to_update
                        try:
                            r = requests.post('http://api.diffbot.com/v3/%s' % job_type, data=job)
                        except:
                            success = False
                            flash("Error restoring a job.")
                if success == True:
                    flash("Restored crawl data")

            else:

                #update rules
                headers = {
                    "Accept":"application/json",
                    "Content-Type": "application/json"
                }
                postUrl = "http://api.diffbot.com/v3/custom?token=%s&bypass=true" % token_to_update
                try:
                    r2 = requests.post(postUrl,headers=headers,data=fetchdata)
                    print r2.text
                    if r2.status_code == 304:
                        success = False
                    elif r2.status_code == 200:
                        success = True
                        flash("Successfully restored rules to %s." % token_to_update)
                except:
                    success = False
                if success==False:
                    flash("Error restoring rules.")

    # get a token if you can get one
    token = None
    backupType = "crawl"
    if "custom" in url:
        token = url.split('/')[-1]
        backupType = "custom"
    elif "nightly" in url:
        token = url.split('/')[-1].replace('.txt','')
    elif "deleted" in url:
        token = url.split('/')[-1].split('-')[0]

    return render_template('tools/backup.html',
        fetchdata=fetchdata,
        token=token,
        backupType=backupType,
        tokenForm=tokenForm,
        url=url
    )

@tools_app.route("/tools/newtoken", methods=["GET","POST"])
@login_required
def newtoken():
    # generate child tokens

    tokenForm = NewToken(request.form)

    """ NewToken.plan.choices is defined as a Class attribute in "forms.py", so that with every run of choices.append() below this array grows and is
    never reset.  Our code here expects an empty plan.choices array, so we empty the array manually on the line below."""
    tokenForm.plan.choices = []

    all_plans = Plans.query.all()
    for plan in all_plans:
        tokenForm.plan.choices.append((plan.name,plan.name.capitalize()))

    if request.method == 'POST' and tokenForm.validate():
        name = tokenForm.name.data
        email = tokenForm.email.data
        notes = tokenForm.notes.data
        plan = tokenForm.plan.data

        tokens = genToken(1)

        db = Database()
        for token in tokens:

            i1 = db.insert("INSERT INTO api (token,name,email,plan,reason) VALUES (%s,%s,%s,%s,%s)" , token,name,email,plan,notes)

        return render_template('tools/newtoken.html',tokenForm=tokenForm,tokens=tokens)

    return render_template('tools/newtoken.html',tokenForm=tokenForm)

@tools_app.route("/tools/rulescopy", methods=["GET","POST"])
@login_required
def rulescopy():

    tokenForm = TokenCopy(request.form)
    success = None

    if request.method == 'POST' and tokenForm.validate():

        token1 = tokenForm.token1.data
        token2 = tokenForm.token2.data

        previewUrl2 = "http://api.diffbot.com/v3/custom?token=%s" % token2

        if token1 == "DELETE":
            j = []

        else:
            previewUrl1 = "http://api.diffbot.com/v3/custom?token=%s" % token1

            try:
                r = requests.get(previewUrl1)
                j = r.json()
            except:
                success = False

            if 'errorCode' in j:
                success = False

        #update rules

        headers = {
            "Accept":"application/json",
            "Content-Type": "application/json"
        }

        postUrl = "http://api.diffbot.com/v3/custom?token=%s&bypass=true" % token2

        try:
            r2 = requests.post(postUrl,headers=headers,data=json.dumps(j))
            if r2.status_code == 304:
                success = "noupdate"
            elif r2.status_code == 200:
                success = True
        except:
            success = False

        return render_template('tools/rulescopy.html', tokenForm=tokenForm, success=success, previewUrl2=previewUrl2)

    else:

        return render_template('tools/rulescopy.html', tokenForm=tokenForm)


@tools_app.route("/tools/request", methods=["GET"])
@tools_app.route("/tools/request/<path>", methods=["GET"])
def req(path=None):
    qs = request.args

    params=""
    headers=None

    try:
        url = qs['url']
    except:
        return json.dumps({"error": "Please supply a valid URL"})

    try:
        api = qs['api']
    except:
        return json.dumps({"error": "Please supply an API"})

    try:
        token = qs['token']
    except:
        token = 'diffbotlabstoken'

    for k,v in qs.items():
        if k not in ['url','api']:
            if v != "":
                params += "&%s=%s" % (k,v)
            else:
                params += "&%s" % k

    # Special Requests: POST

    if path == "post":
        html = getHtml(url)
        headers = {'Content-Type':'text/html'}
        postUrl = "http://api.diffbot.com/v3/%s?token=%s&url=%s&admin&stats" % (api,token,encodeUrl(url))
        r = requests.post(postUrl,headers=headers,data=html)
        try:
            j = r.json()
        except:
            j = {'error':r.text}
        return json.dumps(j)

    # Specific Renderer

    if path == "renderer":
        renderers = getRenderers()
        renderer = "http://%s:14629/cgi-bin/render-cgi2.sh" % random.choice(renderers)
        params += "&renderer=%s" % renderer

    # User Agent
    if path == "useragent":
        headers = {
            'X-Forward-User-Agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_4) AppleWebKit/537.77.4 (KHTML, like Gecko) Version/7.0.5 Safari/537.77.4",
        }

    # Referer
    if path == "referer":
        headers = {
            'X-Forward-Referer': "news.google.com"
        }

    if path == "slowscroll":
        token = "diffbotlabstokenrules"

    # proxy
    if path == "proxy":
        fullProxy = getProxy()
        proxyAuth = fullProxy.split('@')[0]
        proxy=fullProxy.split('@')[1]
        params += '&proxy=%s&proxyAuth=%s' % (proxy,proxyAuth)

    d = diffbotRequest(url,api,parameters=params,token=token,headers=headers)

    if "error" in d:
        pass
    else:
        j = {
            "time":d['time'],
            "response": d['json']
        }

    return json.dumps(j)

@tools_app.route("/tools/archiver", methods=["POST","GET"])
@login_required
def archiver():

    archiveForm = Archiver(request.form)

    if request.method == 'POST' and archiveForm.validate():

        urls = archiveForm.urls.data
        list_of_urls = urls.replace('\r','').split('\n')

        jsonout = []

        for a in list_of_urls:
            if a.startswith("http"):
                item = {}
                if "||" in a:
                    item["url"] = a.split("||")[0]
                    item["notes"] = a.split("||")[1]
                else:
                    item["url"] = a
                jsonout.append(item)

        if len(jsonout) > 0:

            newId = str(time.time()).replace('.','_')
            with codecs.open('static/%s.archives' % newId,'w+','utf-8') as f:
                f.write(json.dumps(jsonout))
            return redirect('/tools/archiver?archives=%s' % newId)

        else:
            flash("No valid links found")
            return render_template('tools/archiver.html', archiveForm=archiveForm)

    else:
        archives = request.args.get('archives')
        archiveError = False
        if archives:
            try:
                r = requests.get('http://backup.diffbot.com/labsassets/archives/%s.archives' % archives)
                archives = r.json()
            except:
                archiveError = True
        return render_template('tools/archiver.html', archiveForm=archiveForm, archives=archives,archiveError=archiveError)


@tools_app.route("/tools/save", methods=["POST"])
def save():

    data = request.get_data().decode('ascii','ignore')
    newId = str(time.time()).replace('.','_')

    data = data.replace('href="/static/','href="http://labs.diffbot.com/static/')
    data = data.replace('src="/static/','src="http://labs.diffbot.com/static/')
    #connect to S3
    key = 'AKIAJ7EESYFLFLWA7HIA'
    secret = 'aGflGMbo4Xh5b0zYvkEfhjpLtbEVB1Di66eL88om'

    conn = tinys3.Connection(key,secret,endpoint='s3-us-west-1.amazonaws.com')
    bucket = 'backup.diffbot.com/labsassets'

    with codecs.open('static/data/%s.html' % newId,'w+','utf-8') as f:
        f.write(data.decode('utf-8'))
        conn.upload('%s.html' % newId,f,bucket)

    message = {}
    message['message'] = "Successfully saved file"
    message['id'] = newId
    message['path'] = "http://%s/%s.html" % (bucket,newId)

    return json.dumps(message)

@tools_app.route("/tools/saved/<i>")
def saved(i):

    d = codecs.open('static/data/%s.html' % i, 'r', 'utf-8')
    data = d.read()

    return render_template('tools/saved.html', data=data)


@tools_app.route("/tools/logs")
@login_required
def logs(token=None):
    """Interface to query logs on BigQuery"""

    token = request.args.get('token')

    dates = [
        datetime.datetime.today().strftime("%Y-%m-%d 00:00:00"),
        datetime.datetime.today().strftime("%Y-%m-%d 23:59:59")
    ]

    queries = db.session.query(LogQuery).order_by(LogQuery.label)
    return render_template('tools/logs.html', queries=queries,token=token,dates=dates)



@tools_app.route("/tools/logs/query", methods=["POST"])
@login_required
def logs_query():
    """Submit a query"""
    query = request.form['query']
    max_results = int(request.form['max_results'])
    start_index = int(request.form['start_index'])
    try:
        query_results = make_query(query)
    except QueryError as e:
        return jsonify(error=str(e))
    rows, total, _ = query_results.fetch_data(max_results=max_results, start_index=start_index)
    schema = [field.name for field in query_results.schema]
    return jsonify(rows=rows, total=total, schema=schema)


@tools_app.route("/tools/logs/download", methods=["POST"])
@login_required
def logs_download():
    """Download a query"""
    query = request.form['query']
    max_results = 1000
    try:
        query_results = make_query(query)
    except QueryError as e:
        raise InvalidUsage(str(e))

    def list_to_csv(l):
        """Convert this list to a CSV formatted string"""
        line = StringIO.StringIO()
        writer = csv.writer(line)
        writer.writerow(l)
        line.seek(0)
        return line.read()

    def iter_results():
        """Download all results for this query in an iterator to avoid holding in memory at once"""
        page_token = None
        for page in itertools.count():
            rows, _, page_token = query_results.fetch_data(max_results=max_results, page_token=page_token)
            if page == 0:
                yield list_to_csv([field.name for field in query_results.schema])
            for row in rows:
                yield list_to_csv(row)
            if not page_token:
                break # reached last page of results

    response = Response(iter_results(), mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=results.csv'
    return response



class QueryError(Exception):
    pass

def make_query(query):
    # load the big query auth settings
    auth_key_path = os.path.join(current_app.config['ROOT_DIR'], 'private/BigQueryAuthKey.json')
    bigquery_client = bigquery.Client.from_service_account_json(auth_key_path, current_app.config['BIG_QUERY_PROJECT'])
    # unique ID for this query
    query_id = str(uuid.uuid4())
    # create a job to execute this query
    job = bigquery_client.run_async_query('job_{}'.format(query_id), query)
    job.begin()
    while job.state != u'DONE':
        # poll until job query is complete
        time.sleep(0.1)
        job.reload()
    if job.error_result:
        # query failed - return error message
        raise QueryError(job.errors[0]['reason'])
    return job.results()


@tools_app.route("/tools/logs/add", methods=["POST"])
@login_required
def logs_add():
    """Save a new log entry with this label"""
    label, query = request.form['label'], request.form['query']
    # delete any existing queries with this label
    db.session.query(LogQuery).filter_by(label=label).delete()
    # now add the new query
    e = LogQuery(label, query)
    db.session.add(e)
    db.session.commit()
    return jsonify(success=True, id=e.id)

@tools_app.route("/tools/test")
def logs_test():
    raise InvalidUsage('This view is gone', status_code=410)


@tools_app.route("/tools/logs/delete/<int:log_query_id>")
@login_required
def logs_delete(log_query_id):
    """Delete log entry with this id"""
    e = db.session.query(LogQuery).filter_by(id=log_query_id).first()
    if e:
        db.session.delete(e)
        db.session.commit()
        success = True
    else:
        success = False
    return jsonify(success=success)


@tools_app.route('/tools/modifyplan', methods=['GET', 'POST'])
@login_required
def modifyplan():
    form1 = ModifyPlan(request.form)
    form2 = AddPlan(request.form)

    db = Database()

    plans = db.call('SELECT name,calls_included,price_month,price_overage,minBulkUrls,dql_quota,dql_facet_quota,enhance_quota,enhance_refresh_quota,rate,nl_quota,nl_rate,stripe_plan_id FROM plan ORDER BY LOWER (name)')
    #plan_names = [ sub[0] for sub in plans ] 
    field_names = [ "name", "calls_included", "price_month", "price_overage", "minBulkUrls", "dql_quota", "dql_facet_quota", "enhance_quota", "enhance_refresh_quota", "rate", "nl_quota", "nl_rate", "stripe_plan_id" ]

    #formClass = "\n".join(form.keys)
    #f = open("demofile3.txt", "w")
    #f.write(formClass)
    #f.close()

    if request.method == 'POST': 
        if form1.validate():

            f = open("demofile2.txt", "w")
            f.write("START1")
            f.close()
            #user = User(form.username.data, form.email.data, form.password.data)
            #db_session.add(user)
            #flash('Thanks for registering')
            #return redirect(url_for('login'))
            plan_name = request.form['plan_to_modify']
            field_name = request.form['field_to_modify']
            new_val = request.form['new_value']
            query = 'UPDATE plan SET %s=%s WHERE name="%s"'%(field_name, new_val, plan_name)

            f = open("queries.log", "a")
            f.write(query + "\n")
            f.close()
            
            #f = open("demofile3.txt", "w")
            #f.write(query)
            #f.close()
            update = db.insert(query)
            #modifplan = Plans.query.filter_by(username='admin').update(dict(email='my_new_email@example.com')))
            return redirect('/tools/modifyplan')
        elif form2.validate():
            name = "'%s'"%(request.form["addplan_name"])
            calls_included = request.form["addplan_calls_included"]
            price_month = request.form["addplan_price_month"]
            price_overage = request.form["addplan_price_overage"]
            minBulkUrls = request.form["addplan_minBulkUrls"]
            dql_quota = request.form["addplan_dql_quota"]
            dql_facet_quota = request.form["addplan_dql_facet_quota"]
            enhance_quota = request.form["addplan_enhance_quota"]
            enhance_refresh_quota = request.form["addplan_enhance_refresh_quota"]
            rate = request.form["addplan_rate"]
            nl_quota = request.form["addplan_nl_quota"]
            nl_rate = request.form["addplan_nl_rate"]
            stripe_plan_id = request.form["addplan_stripe_plan_id"]
            stripe_plan_id = "'%s'"%(stripe_plan_id) if len(stripe_plan_id) > 0 else stripe_plan_id

            allFields = [["name", name], ["calls_included", calls_included], ["price_month", price_month], ["price_overage", price_overage], ["minBulkUrls", minBulkUrls], ["dql_quota", dql_quota], ["dql_facet_quota", dql_facet_quota], ["enhance_quota", enhance_quota], ["enhance_refresh_quota", enhance_refresh_quota], ["rate", rate], ["nl_quota", nl_quota], ["nl_rate", nl_rate], ["stripe_plan_id", stripe_plan_id]]
            
            allFieldsNotEmpty = filter(lambda x: len(x[1]) > 0, allFields) # remove fields that were left blank on the form

            field_names = ", ".join([item[0] for item in allFieldsNotEmpty])
            values = ",".join([item[1] for item in allFieldsNotEmpty])

            query = "INSERT into plan (%s) VALUES (%s);"%(field_names, values)

            f = open("queries.log", "a")
            f.write(query + "\n")
            f.close()

            update = db.insert(query)

            return redirect('/tools/modifyplan')
        
    return render_template('tools/modifyplan.html', form1=form1, plans=plans, field_names=field_names, form2=form2)

#@tools_app.route("/tools/manageplans", methods=["GET", "POST"])
#@tools_app.route("/tools/manageplans/<plan>", methods=["GET","POST"])
#@login_required
#def modifyplan(plan=None):
#
#    db = Database()
#
#    #if request.method == 'POST' and plansForm.validate() and plan:
#    #    update = db.insert("UPDATE plan SET notes=%s WHERE token = %s LIMIT 1" , finalnotes,plan)
#
#    plans = db.call('SELECT name,calls_included,price_month,price_overage,minBulkUrls,dql_quota,dql_facet_quota,enhance_quota,enhance_refresh_quota,rate,nl_quota,nl_rate,stripe_plan_id FROM plan ORDER BY LOWER (name)')
#
#    plan_names = [ sub[0] for sub in plans ] 
#
#    #outArray = "\n".join(plan_names)
#    #text_file = open("sample.txt", "wt")
#    #n = text_file.write(outArray)
#    #text_file.close()
#
#    field_names = [ "name", "calls_included", "price_month", "price_overage", "minBulkUrls", "dql_quota", "dql_facet_quota", "enhance_quota", "enhance_refresh_quota", "rate", "nl_quota", "nl_rate", "stripe_plan_id" ]
#
#    return render_template('tools/modifyplan.html',plans=plans,plan_names=plan_names, field_names=field_names)