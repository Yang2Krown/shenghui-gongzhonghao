from app.api.v1.commercial import _commercial_subject


def test_groups_tencent_products_separately():
    marvis = _commercial_subject({"commercial_brand": "腾讯", "product": "Marvis"})
    miora = _commercial_subject({"commercial_brand": "腾讯", "product": "Miora设计Agent"})

    assert marvis == ("腾讯 marvis", "腾讯 Marvis", "Marvis")
    assert miora == ("腾讯 miora", "腾讯 Miora", "Miora")
    assert marvis[0] != miora[0]


def test_invalid_brand_falls_back_to_product():
    key, display, product = _commercial_subject({
        "commercial_brand": "无法判断",
        "product": "讯飞星辰 MaaS 平台",
    })

    assert key == "讯飞星辰 maas"
    assert display == "讯飞星辰 MaaS"
    assert product == "讯飞星辰 MaaS"
