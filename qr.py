import qrcode

url = "https://donite-maintenance-17.onrender.com/forklift_daily"

img = qrcode.make(url)

img.save("report_qr.png")