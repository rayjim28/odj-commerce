# Store owner handoff

ODJ Group LLC runs the storefront through the admin dashboard at [odjgroupllc.com/admin](https://odjgroupllc.com/admin). Products and business decisions are managed there; routine changes do not require a developer or code changes.

**Current state:** Production is deployed, but public checkout is intentionally closed until the owner has completed the remaining launch requirements and confirms approval. Do not use the site to accept customer money before that process is complete.

## Store owner responsibilities

The owner controls:

- Product descriptions, photos, categories, stock, prices, and which products are published
- Customer support email and phone number
- Standard and express shipping prices, supported destinations, shipping promises, and returns/refund policies
- Stripe Tax registrations and product tax treatment, with tax advice where appropriate
- Fulfillment, shipment tracking, and customer support requests
- Final approval to open or pause checkout

In **Admin → Inventory**, add a product with a valid price and available stock, then publish it. Products left in draft are not purchasable. Uploaded images should use the admin photo uploader.

In **Admin → Store settings**, enter the support email and approved shipping/return policies. Review the actual shipping rates before confirming them.

## Opening checkout

1. Confirm the store has at least one published, in-stock product and complete support/policy details.
2. Review payment and tax settings, shipping rates, and applicable registrations. The maintainer verifies the corresponding server settings.
3. Open **Admin → Launch checklist**. **System checks** report the application's observed configuration and records. **Owner verification checklist** holds signed-off business and manual testing reviews. These are separate; ticking an owner box does not prove a Stripe webhook was delivered.
4. Complete the required owner confirmations only after the underlying work has been verified.
5. Read the final approval statement and select **Open public checkout**. The application will not allow activation while mandatory conditions are missing.

The maintainer's `SALES_ENABLED` setting in Render also has to permit checkout. It is an emergency off switch, **not** a replacement for owner approval. The owner can pause ordering immediately from the same admin page.

## Orders, payments, and refunds

Customers sign in and verify their email before making real purchases. Stripe hosts the payment page. Shipping choices are passed to checkout, and applicable tax is calculated by the owner's Stripe Tax configuration.

The owner can review paid orders and update carrier, tracking number, and fulfillment in **Admin → Orders**. Do not mark an order shipped until it has actually shipped.

Stripe refunds must be issued through the authorized payment provider. ODJ records refund notifications on newer orders, and **Sync Stripe refunds** reads Stripe's history for older payments. That button never issues a new charge or refund. A refunded order does not automatically restock items or authorize a shipment.

The original internal $1 test payment has been refunded and reconciled in ODJ. **Do not ship this test order or issue another refund.** That historic reconciliation does not establish that a fresh refund webhook is currently delivered; the app tracks that separately.

## Owner launch acceptance

The following must be reviewed before accepting actual orders:

- Catalog, price, inventory, product images, and checkout behavior
- Payment acceptance, tax outcome, shipping choices, and order confirmation
- Fulfillment status and refund handling
- Customer account access, email delivery, and password recovery
- Photo persistence after deployment, database/media backup and recovery
- A test-mode refund notification delivered to the receiving application

The owner may check off manually reviewed tasks in the dashboard after the work is completed. The developer should keep the production sales gate closed until the material real-provider checks are finished.

## Maintenance and support

For technical changes, refer to [Operations](docs/OPERATIONS.md) and [Testing](docs/TESTING.md). Credential rotation, Render deployment, database recovery, and payment-webhook configuration belong to the technical maintainer; product listings, policies, and fulfillment belong to ODJ Group.

The dashboard's green indicators do not replace legal compliance review or a production acceptance test.
