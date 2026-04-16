# Business rules — do not hardcode these elsewhere; always import.
VOUCHER_MIN_POINTS = 250          # Minimum points to redeem an Amazon Voucher
VOUCHER_POINTS_TO_INR = 4         # Amazon Voucher: 1 point = ₹4
# Note: physical gifts have their own gift_value_inr in the catalog table
# (effectively 1:5, but always read from DB — never recompute from points)
