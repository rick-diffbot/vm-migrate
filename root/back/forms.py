from flask.ext.wtf import Form
from wtforms import TextField, BooleanField, validators, SelectField, IntegerField, TextAreaField, HiddenField, StringField
from models import Plans
from wtforms.ext.sqlalchemy.fields import QuerySelectField

class URL(Form):
    url = TextField(
        label='URL to test',
        description="URL_entry",
        validators=[
            validators.required(),
            validators.url()
            ]
        )
    token = TextField(label='Token', description="Token (optional)")
    num = IntegerField(default="20",label='Number', description="Number of calls to make", validators=[validators.required(),validators.NumberRange(min=1,max=10000,message="Please enter a number")])
    params = TextField(label='params', description="Parameters (optional)")
    api = SelectField("API",
        choices=[
            ('analyze',"Analyze"),
            ('article',"Article"),
            ('discussion',"Discussion"),
            ('image',"Image"),
            ('product',"Product"),
            ('video',"Video"),
        ],
        validators=[
            validators.required()
            ]
        )

class URLDebug(Form):
    url = TextField(
        label='URL to test',
        description="URL_entry",
        validators=[
            validators.required(),
            validators.url()
            ]
        )
    token = TextField(label='Token', description="Token (optional)")

    api = SelectField("API",
        choices=[
            ('analyze',"Analyze"),
            ('article',"Article"),
            ('discussion',"Discussion"),
            ('image',"Image"),
            ('product',"Product"),
            ('video',"Video"),
        ],
        validators=[
            validators.required()
            ]
        )

class TokenCopy(Form):

    token1 = TextField(label='Copy from Token', description="Token to copy from")
    token2 = TextField(label='Copy to Token', description="Token to copy to")

class ReplaceToken(Form):

    old_token = TextField(label='Old Token', validators=[validators.required()])
    new_token = TextField(label='New Token', validators=[validators.required()])

class ChildTokens(Form):

    parent = TextField(label='Parent Token', description="Parent Token")
    tokenType = SelectField("Token Type",
        choices=[
            ("0","Child"),
            ("1","Replacement")
        ],
        validators=[
            validators.required()
            ]
        )
    num = SelectField("Number",
        choices=[
            ("1","1"),
            ("2","2"),
            ("3","3"),
            ("4","4"),
            ("5","5"),
            ("6","6"),
            ("7","7"),
            ("8","8"),
            ("9","9"),
        ],
        validators=[
            validators.required()
            ]
        )

class NewToken(Form):

    name = TextField(label='Name', validators=[validators.required()])
    email = TextField(label='Email', validators=[validators.required(), validators.Email()])
    notes = TextField(label='Notes')
    plan = SelectField("Plan",
                       choices=[],
                       validators=[
                           validators.required()
                       ]
                       )

class ViewInRenderer(Form):

    url = TextField(label='URL', description="URL",validators=[validators.required()])
    args = TextField(label='Arguments', description="Additional arguments")

class TestDrive(Form):
    token = TextField(label='Token', description="Token")
    otherArgs = TextField(label='Other Arguments', description="Other Arguments")
    url = TextField(label='URL', description="URL",validators=[validators.required()])
    proxySet = SelectField("proxySet",choices=[],validators=[],coerce=str)
    manualProxy = TextField(label='Manual Proxy', description="Manual Proxy")
    headers = TextAreaField(label='Custom Headers', description="List of Jobs to Delete")
    xeval = TextAreaField(label='X-Evaluate', description="List of Jobs to Delete")
    xeval_placeholder = TextAreaField(label='X-Evaluate Placeholder', description="List of Jobs to Delete")
    api = SelectField("API",
        choices=[
            ('renderer',"View in Renderer"),
            ('api_dom',"View API Rendered DOM"),
            ('analyze',"Analyze"),
            ('article',"Article"),
            ('discussion',"Discussion"),
            ('image',"Image"),
            ('product',"Product"),
            ('video',"Video"),
            ('td_analyze',"Analyze (Public Test Drive)"),
            ('td_article',"Article (Public Test Drive)"),
            ('td_discussion',"Discussion (Public Test Drive)"),
            ('td_image',"Image (Public Test Drive)"),
            ('td_product',"Product (Public Test Drive)"),
            ('td_video',"Video (Public Test Drive)")
        ],
        validators=[
            validators.required()
            ]
        )
class SingleInput(Form):

    term = TextField(label='Search Term', description="Search Term")

class RetrieveDBInfo(Form):
    numRetrieve = TextField(label='Number of DB Items to Get', description="db_get", validators=[validators.required(), validators.Regexp('^\d{1}$',message=u'Enter a number between 1 and 10')])

class JobDelete(Form):
    token = TextField(label='Token', description="Token")
    jobs = TextAreaField(label='Job List', description="List of Jobs to Delete")

class CustomPlans(Form):

    notes = TextAreaField(label='Notes', description="Notes")

class Archiver(Form):

    urls = TextAreaField(label='Archives', description="Archives")

class Accounts(Form):
    token = TextField(label='Token',validators = [validators.required()])
    name = TextField(label='Name',validators = [validators.required()])
    reason = TextField(label='Reason')
    email = TextField(label='Email',validators = [validators.required(), validators.Email(message=u'Please enter a valid email address.')])
    created = TextField(label='Token',validators = [validators.required()])
    immediately = BooleanField(label="immediately")
    cancelStripe = SelectField("cancelStripe",
        choices=[
            ('0','No'),
            ('1','Yes, at end of billing period'),
            ('2','Yes, immediately')
        ]
    )
    blocked = SelectField("blocked",
        choices=[
            ('0','Active'),
            ('1','Blocked'),
        ],
        validators=[
            validators.required()
        ]
    )

class AccountChange(Form):
    retroactive = BooleanField(label="retroactive")
    plan = SelectField("plan",choices=[],validators=[],coerce=str)

class Discount(Form):
    retroactive = BooleanField(label="retroactive")
    length = SelectField("length",
        choices=[
            ("2","2 months"),
            ("3","3 months"),
            ("6","6 months"),
            ("9","9 months"),
            ("12","12 months")
        ],validators=[
            validators.required()
        ])

    coupon = SelectField("coupon",
            choices=[
                ('25percent',"25%"),
                ('33percent',"33%"),
                ('50percent',"50%"),
                ('66percent',"66%"),
                ('75percent',"75%"),
                ('9967',"$99.67"),
                ('14950',"$149.50"),
                ('44950',"$449.50"),
                ('199950',"$1999.50")
            ],
            validators=[
                validators.required()
                ]
            )
class Invoices(Form):

    id = HiddenField(label='id')
    cm_extid = HiddenField(label='ChartMogul External ID')
    parent = HiddenField(label='Renewal parent ID')
    name = TextField(label='Name',validators = [validators.required()])
    cm_uuid = TextField(label='ChartMogul UUID')
    cm_subid = TextField(label='ChartMogul Subscription ID')
    amount = TextField(label='Amount Billed',validators = [validators.required()])
    length = TextField(label='Length in months')
    start = TextField(label='Congract Start Date',validators = [validators.required()])
    end = TextField(label='Contract End Date')
    cancel = TextField(label='Cancellation Date')
    note = TextField(label="Additional note",validators = [validators.Length(max=25)])
    type = SelectField("type",
        choices=[
            ('subscription',"Subscription"),
            ('one_time',"One-Time Charge")
        ],
        validators=[
            validators.required()
            ]
        )
    interval = SelectField("interval",
        choices=[
            ('monthly',"Monthly")
        ],
        validators=[
            validators.required()
            ]
        )
    token = TextField(label='Token')
    email = TextField(label='Email',)
    account_manager = TextField(label='Account Manager')

class ModifyPlan(Form):
    plan_to_modify = SelectField('Plan to Modify', choices=[])
    field_to_modify = SelectField('Field to Modify', choices=[])
    new_value = StringField('New Value', [validators.required()])
    field_names = [ "name", "calls_included", "price_month", "price_overage", "minBulkUrls", "dql_quota", "dql_facet_quota", "enhance_quota", "enhance_refresh_quota", "rate", "nl_quota", "nl_rate", "stripe_plan_id" ]

    def __init__(self, *args, **kwargs):
        super(ModifyPlan, self).__init__(*args, **kwargs)

        field_names = [ "name", "calls_included", "price_month", "price_overage", "minBulkUrls", "dql_quota", "dql_facet_quota", "enhance_quota", "enhance_refresh_quota", "rate", "nl_quota", "nl_rate", "stripe_plan_id" ]
        self.plan_to_modify.choices = [(p.name, p.name) for p in Plans.query.all()]
        self.field_to_modify.choices = [(p, p) for p in field_names]

class AddPlan(Form):
    addplan_name = StringField(label='name', validators=[validators.required()])
    addplan_calls_included = IntegerField(label='calls_included', validators=[validators.NumberRange(min=0,max=9999999999,message="Please enter a number between 0 and 9,999,999,999")])
    addplan_price_month = IntegerField(label='price_month', validators=[validators.NumberRange(min=0,max=9999999999,message="Please enter a number between 0 and 9,999,999,999")])
    addplan_price_overage = IntegerField(label='price_overage', validators=[validators.NumberRange(min=0,max=9999999999,message="Please enter a number between 0 and 9,999,999,999")])
    addplan_minBulkUrls = IntegerField(label='minBulkUrls', validators=[validators.NumberRange(min=0,max=9999999999,message="Please enter a number between 0 and 9,999,999,999")])
    addplan_dql_quota = IntegerField(label='dql_quota', validators=[validators.required(),validators.NumberRange(min=0,max=9999999999,message="Please enter a number between 0 and 9,999,999,999")])
    addplan_dql_facet_quota = IntegerField(label='dql_facet_quota', validators=[validators.required(),validators.NumberRange(min=0,max=9999999999,message="Please enter a number between 0 and 9,999,999,999")])
    addplan_enhance_quota = IntegerField(label='enhance_quota', validators=[validators.required(),validators.NumberRange(min=0,max=9999999999,message="Please enter a number between 0 and 9,999,999,999")])
    addplan_enhance_refresh_quota = IntegerField(label='enhance_refresh_quota', validators=[validators.required(),validators.NumberRange(min=0,max=9999999999,message="Please enter a number between 0 and 9,999,999,999")])
    addplan_rate = IntegerField(label='rate', validators=[validators.required(),validators.NumberRange(min=0,max=9999999999,message="Please enter a number between 0 and 9,999,999,999")])
    addplan_nl_quota = IntegerField(label='nl_quota', validators=[validators.required(),validators.NumberRange(min=0,max=9999999999,message="Please enter a number between 0 and 9,999,999,999")])
    addplan_nl_rate = IntegerField(label='nl_rate', validators=[validators.required(),validators.NumberRange(min=0,max=9999999999,message="Please enter a number between 0 and 9,999,999,999")])
    addplan_stripe_plan_id = StringField(label='stripe_plan_id', validators=[])