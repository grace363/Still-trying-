```javascript
const axios = require('axios');

class PaymentService {
  async processMpesaPayment(payment) {
    try {
      const response = await axios.post(
        `${process.env.MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest`,
        {
          BusinessShortCode: process.env.MPESA_SHORTCODE,
          Password: process.env.MPESA_PASSWORD,
          Timestamp: new Date().toISOString().replace(/[^0-9]/g, '').slice(0, -3),
          TransactionType: 'CustomerPayBillOnline',
          Amount: payment.amount,
          PartyA: payment.accountDetails,
          PartyB: process.env.MPESA_SHORTCODE,
          PhoneNumber: payment.accountDetails,
          CallBackURL: `${process.env.BASE_URL}/api/payments/mpesa/callback`,
          AccountReference: `PAY-${payment._id}`,
          TransactionDesc: 'WatchEarn Payment'
        },
        {
          headers: {
            'Authorization': `Bearer ${process.env.MPESA_ACCESS_TOKEN}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      return response.data;
    } catch (error) {
      throw new Error(`M-Pesa payment failed: ${error.message}`);
    }
  }

  async processPayPalPayment(payment) {
    try {
      const response = await axios.post(
        `${process.env.PAYPAL_BASE_URL}/v1/payments/payouts`,
        {
          sender_batch_header: {
            sender_batch_id: `batch-${payment._id}`,
            email_subject: 'You have a payout!',
            email_message: 'You have received a payout from WatchEarn!'
          },
          items: [{
            recipient_type: 'EMAIL',
            amount: {
              value: payment.amount.toString(),
              currency: 'USD'
            },
            receiver: payment.accountDetails,
            note: 'Payment from WatchEarn',
            sender_item_id: `item-${payment._id}`
          }]
        },
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${process.env.PAYPAL_ACCESS_TOKEN}`
          }
        }
      );
      
      return response.data;
    } catch (error) {
      throw new Error(`PayPal payment failed: ${error.message}`);
    }
  }
}

module.exports = new PaymentService();
```
