
function calculateTotalAmounts(orders, numbers) {
    if (orders.lenth <= 0) return numbers
    return numbers.map((number, index) => {
        const total = orders
            .filter(order => new Date(order.date_order).getDate() === index + 1)
            .reduce((sum, order) => sum + order.amount_paid, 0);
        return total;
    });
}

function calculateNumberAmounts(orders, numbers) {
    return numbers.map((number, index) => {
        const total = orders
            .filter(order => new Date(order.date_order).getDate() === index + 1)
            .reduce((sum, order) => sum + 1, 0);
        return total;
    });
}

function calculatePriceAmounts(orders, numbers, listorrderline, products) {
    return numbers.map((number, index) => {
        const total = orders
            .filter(order => new Date(order.date_order).getDate() === index + 1)
            .reduce((sum, order) => {
                const orderline = listorrderline.filter((i) => i.order_id[0] == order.id)

                if (orderline.length > 0) {
                    orderline.map((item) => {
                        console.log('p', item.payment_method_id)

                        const product = products.find((i) => i.id == item.product_id[0])
                        console.log(product)

                        if (product) {
                            console.log(product.standard_price, 'product')
                            sum = sum + item.qty * product.standard_price
                        }
                    })
                }
                return sum
            }, 0);
        return total;
    });
}
function subtractArrays(array1, array2) {
    var result = array1.map(function (value, index) {
        return value - array2[index];
    });
    return result;
}


function calculatePriceAmountsProduct(listorrderline, products) {
    return products.map((product, index) => {
        const total = listorrderline
            .filter(order => order.product_id[0] === product.id)
            .reduce((sum, total) => {
                sum = sum + total.price_subtotal
                return sum
            }, 0);
        product.total = total
        return product;
    });
}
function calculatePriceAmountsStaff(listorrderline, Staffs) {
    return Staffs.map((staff, index) => {

        const total = listorrderline
            .filter(order => order.create_uid[0] === staff.id)
            .reduce((sum, total) => {
                sum = sum + total.price_subtotal
                return sum
            }, 0);
        staff.total = total

        return staff;
    });
}


function calculatePriceAmountsCash(listorder, payments) {


    if (listorder.length <= 0) return { total: 0, number: 0 }
    let number = 0
    let amount = 0
    const total = listorder.reduce((sum, item) => {
        const order = payments.find((i) => i.pos_order_id[0] == item.id)
        if (order.payment_method_id[0] == 1) {
            amount = amount + item.amount_paid
            number = number + 1
        }
    }, 0)
    return { total: amount, number: number }
}
function calculatePriceAmountsBank(listorder, payments) {
    if (listorder.length <= 0) return { total: 0, number: 0 }
    let number = 0
    let amount = 0
    const total = listorder.reduce((sum, item) => {
        const order = payments.find((i) => i.pos_order_id[0] == item.id)
        if (order.payment_method_id[0] == 2) {
            amount = amount + item.amount_paid
            number = number + 1
        }

    }, 0)
    return { total: amount, number: number }
}

function calculateNumberAmountsPurchar(orders) {
    if (orders.length <= 0) return 0
    return orders.reduce((sum, item) => sum + item.amount_total, 0);
}

function countCustomers(orders) {
    let customerCount = 0;
    let phoneNumbers = [];
    const list = orders.filter((i) => i.partner_id != false)
    for (let i = 0; i < list.length; i++) {
        const phoneNumber = list[i].partner_id[0];
        if (!phoneNumbers.includes(phoneNumber)) {
            phoneNumbers.push(phoneNumber);
            customerCount++;
        }
    }

    return customerCount;
}
function getUniqueCustomers(orders) {
    console.log(orders)
    const list = orders.filter((i) => i.partner_id != false)
    const uniqueCustomers = [];

    list.forEach((order) => {

        const customer = order.partner_id[0];
        if (!uniqueCustomers.includes(customer)) {
            uniqueCustomers.push(customer);
        }
    });

    return uniqueCustomers;
}