/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Layout } from "@web/views/layout";
import { KeepLast } from "@web/core/utils/concurrency";
import { Model, useModel } from "@web/views/helpers/model";
import { useService } from '@web/core/utils/hooks';
var session = require('web.session');

const { useRef, useState } = owl.hooks
const currentDate = new Date()
const currentMonth = currentDate.getMonth() + 1
const yearCurrent = currentDate.getFullYear()
const startOfMonth = new Date(yearCurrent, currentMonth - 1, 1); // Ngày đầu tháng
const endOfMonth = new Date(yearCurrent, currentMonth, 0); // Ngày cuối tháng

function getDaysInMonth(year, month) {
    return new Date(year, month, 0).getDate();
}
class VeryBasicModel extends Model {
    static services = ["orm"];

    constructor() {
        super(...arguments);

    }
    setup(params, { orm }) {
        this.model = params.resModel;
        this.orm = orm;
        this.keepLast = new KeepLast();
    }

    async load(params) {
        console.log(params, this.env)
        this.stafflist = await this.keepLast.add(
            this.orm.searchRead("hr.employee", params.domain, [])
        );

        // const currency_id = company_id.currency_id
        // this.currency_symbol = currency_id.symbol
        this.notify();
    }
}
VeryBasicModel.services = ["orm"];

class VeryBasicView extends owl.Component {
    inputRef = useRef("chart1");
    inputRef2 = useRef("chart2");
    inputRef3 = useRef("chart3");

    month = useRef("month");
    staff = useRef("staff")
    // state = {
    //     monthValue: "",
    //     staffValue: 0,
    //     numberDate: 0,
    //     lableChart1: [],
    //     listCustomer: [],
    //     month: currentMonth,
    //     startOfMonth: startOfMonth,
    //     endOfMonth: endOfMonth,
    //     year: yearCurrent

    // };
    async setup() {
        this.ormService = useService('orm');
        this.model = useModel(VeryBasicModel, {
            resModel: this.props.resModel,
            domain: this.props.domain,
            orm: this.props.orm,

        });
        this.state = useState({
            monthValue: "",
            staffValue: 0,
            numberDate: 0,
            lableChart1: [],
            listCustomer: [],
            month: currentMonth,
            startOfMonth: startOfMonth,
            endOfMonth: endOfMonth,
            year: yearCurrent,


        })
        const value = `${yearCurrent}-${currentMonth > 10 ? currentMonth : `0${currentMonth}`}`
        this.state.monthValue = value; // Update the default value
        // this.listCustomer = await this.ormService.searchRead("res.partner", [['partner_share', '=', true]]);
        // console.log(this.listCustomer)

    }
    constructor() {
        super(...arguments);


    }
    async getData() {
        console.log(this.state)
        this.listNewCustomer = await this.ormService.searchRead("res.partner", [['create_date', '>=', this.state.startOfMonth],
        ['create_date', '<=', this.state.endOfMonth],]);
        this.listCustomer = await this.ormService.searchRead("res.partner", [['partner_share', '=', true]]);
        this.listOrder = await this.ormService.searchRead("pos.order", [['state', '=', 'paid'], ['date_order', '>=', this.state.startOfMonth],
        ['date_order', '<=', this.state.endOfMonth],]);
        this.listOrderLine = await this.ormService.searchRead("pos.order.line", [['create_date', '>=', this.state.startOfMonth],
        ['create_date', '<=', this.state.endOfMonth],]);
        this.listProduct = await this.ormService.searchRead("product.template", [['detailed_type', '=', 'product']]);
        this.listStaff = await this.ormService.searchRead("hr.employee", [])
        this.listPurchase = await this.ormService.searchRead("purchase.order", [['date_order', '>=', this.state.startOfMonth],
        ['date_order', '<=', this.state.endOfMonth], ['state', '=', 'purchase']])
        const [year, month] = this.month.el.value.split('-');

        // Update the default value
        this.state.numberDate = currentDate.getDate()

        this.listpayment = await this.ormService.searchRead("pos.payment", [['payment_date', '>=', this.state.startOfMonth],
        ['payment_date', '<=', this.state.endOfMonth],]);

        const lable = Array.from({ length: getDaysInMonth(year, month) });
        const labels = lable.map((item, index) => `${this.state.monthValue}-${index + 1}`)

        const arrayTotal = calculateTotalAmounts(this.listOrder, lable)// tông doanh thu
        const arrayTotalNumberOrder = calculateNumberAmounts(this.listOrder, lable,)// số đơn hàng
        const arrayTotalPrice = calculatePriceAmounts(this.listOrder, lable, this.listOrderLine, this.listProduct)// tổng giá vốn
        const arrayprofit = subtractArrays(arrayTotal, arrayTotalPrice)// tổng lợi nhuận
        const products = calculatePriceAmountsProduct(this.listOrderLine, this.listProduct)
        const listStaff = calculatePriceAmountsStaff(this.listOrderLine, this.listStaff)


        const staffSort = listStaff.sort((a, b) => b.total - a.total)
        const staffFinal = staffSort.slice(0, 12)
        const labelStaff = staffFinal.map((item) => item.name)
        const dataStaff = staffFinal.map(item => item.total)

        const productSort = products.sort((a, b) => b.total - a.total)
        const productFinal = productSort.slice(0, 12)
        const labelProduct = productFinal.map((item) => item.name)
        const dataProduct = productFinal.map(item => item.total)

        this.total = arrayTotal.reduce((total, current) => total + current, 0);
        this.numberorder = this.listOrder.length
        this.totalProfit = arrayprofit.reduce((total, current) => total + current, 0);
        this.numberCustomer = countCustomers(this.listOrder)


        const cash = calculatePriceAmountsCash(this.listOrder, this.listpayment)
        this.totalCash = cash.total
        this.numberCash = cash.number
        const bank = calculatePriceAmountsBank(this.listOrder, this.listpayment)
        this.totalBank = bank.total
        this.numberBank = bank.number

        this.numberOldCustomer = this.listCustomer.length - this.listNewCustomer.length
        this.numberNewCustomer = this.listNewCustomer.length

        this.totalPurchase = calculateNumberAmountsPurchar(this.listPurchase)
        this.numberPurchase = this.listPurchase.length

        this.listCustomerInOrder = getUniqueCustomers(this.listOrder)
        this.newCustomer = 0
        this.listCustomer.map((item) => {
            console.log('pppp', item)
            const cus = this.listCustomerInOrder.find((i) => (item.partner_id && item.partner_id[0] == i))
            if (cus) {
                if (cus.sale_order_count == 1) {
                    this.newCustomer += 1
                }
            }
            return item
        })
        this.oldCustomer = this.numberCustomer - this.newCustomer
        console.log("muahg", this.listPurchase)

        this.myChart = new Chart(this.inputRef.el, {

            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    data: arrayTotal,
                    label: 'Revenue',
                    borderColor: '#0e9f6e',
                    fill: false,
                    cubicInterpolationMode: 'monotone',
                    tension: 0.4,
                    pointStyle: 'circle',
                    pointRadius: 1,
                },
                {
                    data: arrayTotalNumberOrder,
                    label: 'Number Order',
                    borderColor: '#00bbcc',
                    fill: false,
                    cubicInterpolationMode: 'monotone',
                    tension: 0.4,
                    pointStyle: 'circle',
                    pointRadius: 1,
                },
                {
                    data: arrayprofit,
                    label: 'Profit',
                    borderColor: '#D81B60',
                    fill: false,
                    cubicInterpolationMode: 'monotone',
                    tension: 0.4,
                    pointStyle: 'circle',
                    pointRadius: 1,
                },

                ]

            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                },

                scales: {
                    x: {
                        grid: {
                            display: false,
                        },
                        ticks: { maxTicksLimit: 10 },
                    },
                    y: {
                        grid: {
                            drawBorder: false,
                            tickLength: 40,
                        },

                        ticks: {
                            max: 250000000,
                            min: 1,
                            stepSize: 30000,

                        },
                    },
                },
            }


        });
        this.myDoughnutChart = new Chart(this.inputRef2.el, {
            type: 'doughnut',
            data: {
                labels: labelProduct,
                datasets: [{
                    data: dataProduct,
                }]
            },
            options: {}


        });
        this.myBarChart = new Chart(this.inputRef3.el, {
            type: 'bar',

            data: {
                labels: labelStaff,
                datasets: [{
                    data: dataStaff,
                    label: 'Revenue',
                }]
            },
            options: {}
        });

        this.render();
    }
    async mounted() {

        this.listNewCustomer = await this.ormService.searchRead("res.partner", [['create_date', '>=', this.state.startOfMonth],
        ['create_date', '<=', this.state.endOfMonth],]);
        this.listCustomer = await this.ormService.searchRead("res.partner", [['partner_share', '=', true]]);
        this.listOrder = await this.ormService.searchRead("pos.order", [['state', '=', 'paid'], ['date_order', '>=', this.state.startOfMonth],
        ['date_order', '<=', this.state.endOfMonth],]);
        this.listOrderLine = await this.ormService.searchRead("pos.order.line", [['create_date', '>=', this.state.startOfMonth],
        ['create_date', '<=', endOfMonth],]);
        this.listProduct = await this.ormService.searchRead("product.template", [['detailed_type', '=', 'product']]);
        this.listStaff = await this.ormService.searchRead("hr.employee", [])
        this.listPurchase = await this.ormService.searchRead("purchase.order", [['create_date', '>=', this.state.startOfMonth],
        ['create_date', '<=', endOfMonth], ['state', '=', 'purchase']])


        this.state.numberDate = currentDate.getDate()

        this.listpayment = await this.ormService.searchRead("pos.payment", [['payment_date', '>=', this.state.startOfMonth],
        ['payment_date', '<=', this.state.endOfMonth],]);

        const lable = Array.from({ length: getDaysInMonth(yearCurrent, currentMonth) });
        const labels = lable.map((item, index) => `${this.state.monthValue}-${index + 1}`)

        const arrayTotal = calculateTotalAmounts(this.listOrder, lable)// tông doanh thu
        const arrayTotalNumberOrder = calculateNumberAmounts(this.listOrder, lable,)// số đơn hàng
        const arrayTotalPrice = calculatePriceAmounts(this.listOrder, lable, this.listOrderLine, this.listProduct)// tổng giá vốn
        const arrayprofit = subtractArrays(arrayTotal, arrayTotalPrice)// tổng lợi nhuận
        const products = calculatePriceAmountsProduct(this.listOrderLine, this.listProduct)
        const listStaff = calculatePriceAmountsStaff(this.listOrderLine, this.listStaff)


        const staffSort = listStaff.sort((a, b) => b.total - a.total)
        const staffFinal = staffSort.slice(0, 12)
        const labelStaff = staffFinal.map((item) => item.name)
        const dataStaff = staffFinal.map(item => item.total)

        const productSort = products.sort((a, b) => b.total - a.total)
        const productFinal = productSort.slice(0, 12)
        const labelProduct = productFinal.map((item) => item.name)
        const dataProduct = productFinal.map(item => item.total)

        this.total = arrayTotal.reduce((total, current) => total + current, 0);
        this.numberorder = this.listOrder.length
        this.totalProfit = arrayprofit.reduce((total, current) => total + current, 0);
        this.numberCustomer = countCustomers(this.listOrder)


        const cash = calculatePriceAmountsCash(this.listOrder, this.listpayment)
        this.totalCash = cash.total
        this.numberCash = cash.number
        const bank = calculatePriceAmountsBank(this.listOrder, this.listpayment)
        this.totalBank = bank.total
        this.numberBank = bank.number

        this.numberOldCustomer = this.listCustomer.length - this.listNewCustomer.length
        this.numberNewCustomer = this.listNewCustomer.length

        this.totalPurchase = calculateNumberAmountsPurchar(this.listPurchase)
        this.numberPurchase = this.listPurchase.length

        this.listCustomerInOrder = getUniqueCustomers(this.listOrder)
        this.newCustomer = 0
        this.listCustomer.map((item) => {
            console.log('pppp', item)
            const cus = this.listCustomerInOrder.find((i) => (item.partner_id && item.partner_id[0] == i))
            if (cus) {
                if (cus.sale_order_count == 1) {
                    this.newCustomer += 1
                }
            }
            return item
        })
        this.oldCustomer = this.numberCustomer - this.newCustomer


        this.myChart = new Chart(this.inputRef.el, {

            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    data: arrayTotal,
                    label: 'Revenue',
                    borderColor: '#0e9f6e',
                    fill: false,
                    cubicInterpolationMode: 'monotone',
                    tension: 0.4,
                    pointStyle: 'circle',
                    pointRadius: 1,
                },
                {
                    data: arrayTotalNumberOrder,
                    label: 'Number Order',
                    borderColor: '#00bbcc',
                    fill: false,
                    cubicInterpolationMode: 'monotone',
                    tension: 0.4,
                    pointStyle: 'circle',
                    pointRadius: 1,
                },
                {
                    data: arrayprofit,
                    label: 'Profit',
                    borderColor: '#D81B60',
                    fill: false,
                    cubicInterpolationMode: 'monotone',
                    tension: 0.4,
                    pointStyle: 'circle',
                    pointRadius: 1,
                },

                ]

            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                },

                scales: {
                    x: {
                        grid: {
                            display: false,
                        },
                        ticks: { maxTicksLimit: 10 },
                    },
                    y: {
                        grid: {
                            drawBorder: false,
                            tickLength: 40,
                        },

                        ticks: {
                            max: 250000000,
                            min: 1,
                            stepSize: 30000,

                        },
                    },
                },
            }


        });
        this.myDoughnutChart = new Chart(this.inputRef2.el, {
            type: 'doughnut',
            data: {
                labels: labelProduct,
                datasets: [{
                    data: dataProduct,
                }]
            },
            options: {}


        });
        this.myBarChart = new Chart(this.inputRef3.el, {
            type: 'bar',

            data: {
                labels: labelStaff,
                datasets: [{
                    data: dataStaff,
                    label: 'Revenue',
                }]
            },
            options: {}
        });

        this.render();
    }

    onClick() {
        const [year, month] = this.month.el.value.split('-');
        this.state.monthValue = this.month.el.value
        this.state.staffValue = this.staff.el.value
        this.state.startOfMonth = new Date(year, month - 1, 1)
        this.state.endOfMonth = new Date(year, month, 0)

        this.state.month = month
        this.state.year = year

        console.log('thang', this.state.endOfMonth.getMonth())
        this.myBarChart.destroy()
        this.myDoughnutChart.destroy()
        this.myChart.destroy()
        this.getData()
        this.render()

    }
    onStop() {
    }


}

VeryBasicView.type = "barcode_view";
VeryBasicView.display_name = "VeryBasicView";
VeryBasicView.icon = "fa-heart";
VeryBasicView.multiRecord = true;
VeryBasicView.searchMenuTypes = ["filter", "favorite"];
VeryBasicView.components = { Layout };
VeryBasicView.template = "chartjs_sale.ChartTemplate";

registry.category("views").add("barcode_view", VeryBasicView);


