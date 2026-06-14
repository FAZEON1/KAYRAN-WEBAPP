import streamlit as st
from datetime import datetime, date

def _css():
    return """
<style>
.hm-tab-active{background:linear-gradient(135deg,rgba(99,102,241,0.25),rgba(139,92,246,0.15));border:1px solid rgba(99,102,241,0.4);border-radius:12px;padding:10px 20px;color:#FFFFFF;font-weight:700;font-size:13px;cursor:pointer;text-align:center;}
.hm-tab-passive{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:10px 20px;color:#64748B;font-weight:500;font-size:13px;cursor:pointer;text-align:center;}
.hm-card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:22px 24px;margin-bottom:16px;}
.hm-result-box{background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.2);border-radius:12px;padding:16px 20px;margin-top:12px;}
.hm-label{font-size:10px;color:#64748B;letter-spacing:1.5px;text-transform:uppercase;font-weight:700;margin-bottom:4px;}
.hm-val{font-size:26px;font-weight:800;color:#FFFFFF;font-family:'JetBrains Mono',monospace;line-height:1.1;}
.hm-val-sm{font-size:18px;font-weight:700;font-family:'JetBrains Mono',monospace;line-height:1.1;}
.hm-val-xs{font-size:14px;font-weight:700;font-family:'JetBrains Mono',monospace;line-height:1.2;}
.hm-sep{height:1px;background:rgba(255,255,255,0.06);margin:20px 0;}
.hm-row{padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.04);}
.prim-card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:22px 24px;margin-bottom:16px;}
.prim-result{background:rgba(16,185,129,0.06);border:1px solid rgba(16,185,129,0.2);border-radius:14px;padding:20px 22px;margin-top:14px;}
.prim-edit-box{background:rgba(99,102,241,0.06);border:1px solid rgba(99,102,241,0.2);border-radius:12px;padding:16px 18px;margin-top:8px;}
[data-testid='stNumberInput'] label,[data-testid='stTextInput'] label,[data-testid='stSelectbox'] label,[data-testid='stDateInput'] label{color:#CBD5E1!important;font-size:11px!important;font-weight:600!important;letter-spacing:.5px!important;text-transform:uppercase!important;}
[data-testid='stNumberInput'] input,[data-testid='stTextInput'] input{background:rgba(255,255,255,0.05)!important;border:1px solid rgba(255,255,255,0.1)!important;color:#FFFFFF!important;border-radius:10px!important;}
[data-testid='stNumberInput'] input:focus,[data-testid='stTextInput'] input:focus{border-color:#6366F1!important;box-shadow:0 0 0 3px rgba(99,102,241,0.15)!important;}
[data-testid='stSelectbox'] > div > div{background:rgba(255,255,255,0.05)!important;border:1px solid rgba(255,255,255,0.1)!important;color:#FFFFFF!important;border-radius:10px!important;}
</style>
"""
def _toplam_maliyet(alis, masraf_tipi, masraf_deger):
    if masraf_tipi == '%':
        return alis * (1 + masraf_deger / 100)
    else:
        return alis + masraf_deger

def _marj(maliyet, satis):
    if satis <= 0: return 0.0
    return (satis - maliyet) / satis * 100

def _kar(maliyet, satis):
    return satis - maliyet

def _fmt(val, prefix='$', decimals=2):
    fmt = '{:,.2f}' if decimals == 2 else '{:,.0f}'
    return prefix + fmt.format(val)

def _renk(kar):
    if kar > 0: return '#10B981'
    if kar < 0: return '#EF4444'
    return '#F59E0B'

def _fmt_tl(val):
    return '{:,.0f} TL'.format(val)

def _fmt_usd(val):
    return '${:,.0f}'.format(val)

def _get_supabase():
    try:
        from supabase import create_client
        url = st.secrets['supabase']['url']
        key = st.secrets['supabase'].get('service_role_key') or st.secrets['supabase'].get('key')
        return create_client(url, key)
    except Exception:
        return None

def prim_gecmis_kaydet(kisi, donem, toplam_prim, odeme_tarihi, notlar=''):
    try:
        sb = _get_supabase()
        if not sb: return False
        sb.table('prim_gecmis').insert({
            'kisi': kisi, 'donem': donem, 'toplam_prim': float(toplam_prim),
            'odeme_tarihi': str(odeme_tarihi), 'notlar': notlar,
            'olusturma_tarihi': datetime.utcnow().isoformat()
        }).execute()
        return True
    except Exception as e:
        st.error('Kayit hatasi: ' + str(e))
        return False

def prim_gecmis_sil(row_id):
    try:
        sb = _get_supabase()
        if not sb: return False
        sb.table('prim_gecmis').delete().eq('id', row_id).execute()
        return True
    except Exception as e:
        st.error('Silme hatasi: ' + str(e))
        return False

def prim_gecmis_guncelle(row_id, donem, toplam_prim, odeme_tarihi, notlar):
    try:
        sb = _get_supabase()
        if not sb: return False
        sb.table('prim_gecmis').update({
            'donem': donem, 'toplam_prim': float(toplam_prim),
            'odeme_tarihi': str(odeme_tarihi), 'notlar': notlar
        }).eq('id', row_id).execute()
        return True
    except Exception as e:
        st.error('Guncelleme hatasi: ' + str(e))
        return False

def prim_gecmis_listele(kisi):
    try:
        sb = _get_supabase()
        if not sb: return []
        res = sb.table('prim_gecmis').select('*').eq('kisi', kisi).order('odeme_tarihi', desc=True).execute()
        return res.data or []
    except Exception:
        return []
def _gecmis_odemeler(kisi, prefix):
    gecmis = prim_gecmis_listele(kisi)
    edit_key = prefix + '_edit_id'
    if edit_key not in st.session_state:
        st.session_state[edit_key] = None

    if gecmis:
        # Tablonun başlıkları
        h1,h2,h3,h4,h5,h6 = st.columns([1.2, 1.8, 1.5, 2.2, 0.6, 0.6])
        for col, bas in zip([h1,h2,h3,h4,h5,h6], ['Dönem','Toplam Prim','Ödeme Tarihi','Not','','']):
            with col: st.markdown('<div class="hm-label">' + bas + '</div>', unsafe_allow_html=True)
        st.markdown('<div style="height:1px;background:rgba(255,255,255,0.08);margin-bottom:6px"></div>', unsafe_allow_html=True)

        silinecek_id = None
        for row in gecmis:
            rid = row.get('id')
            c1,c2,c3,c4,c5,c6 = st.columns([1.2, 1.8, 1.5, 2.2, 0.6, 0.6])
            with c1: st.markdown('<div style="color:#E2E8F0;font-size:13px;padding:6px 0;font-weight:600">' + str(row.get('donem','')) + '</div>', unsafe_allow_html=True)
            with c2: st.markdown('<div style="color:#10B981;font-size:13px;font-weight:700;padding:6px 0">' + _fmt_tl(row.get('toplam_prim',0)) + '</div>', unsafe_allow_html=True)
            with c3: st.markdown('<div style="color:#CBD5E1;font-size:13px;padding:6px 0">' + str(row.get('odeme_tarihi','')) + '</div>', unsafe_allow_html=True)
            with c4: st.markdown('<div style="color:#64748B;font-size:12px;padding:6px 0">' + (row.get('notlar','') or '—') + '</div>', unsafe_allow_html=True)
            with c5:
                if st.button('✏️', key=prefix+'_edit_'+str(rid), help='Düzenle'):
                    st.session_state[edit_key] = rid
                    st.rerun()
            with c6:
                if st.button('🗑️', key=prefix+'_del_'+str(rid), help='Sil'):
                    silinecek_id = rid
            st.markdown('<div style="height:1px;background:rgba(255,255,255,0.04)"></div>', unsafe_allow_html=True)

        if silinecek_id:
            prim_gecmis_sil(silinecek_id)
            st.rerun()

        # Düzenleme formu
        if st.session_state[edit_key] is not None:
            edit_row = next((r for r in gecmis if r.get('id') == st.session_state[edit_key]), None)
            if edit_row:
                st.markdown('<div class="prim-edit-box">', unsafe_allow_html=True)
                st.markdown('<div style="color:#A5B4FC;font-size:11px;font-weight:700;letter-spacing:1px;margin-bottom:12px">KAYDI DÜZENLE</div>', unsafe_allow_html=True)
                e1,e2,e3,e4 = st.columns([1.5,1.5,1.5,2])
                with e1:
                    e_donem = st.text_input('Dönem', value=edit_row.get('donem',''), key=prefix+'_e_donem')
                with e2:
                    e_prim = st.number_input('Prim (TL)', min_value=0.0, value=float(edit_row.get('toplam_prim',0)), step=100.0, format='%.0f', key=prefix+'_e_prim')
                with e3:
                    try:
                        e_tarih_def = date.fromisoformat(str(edit_row.get('odeme_tarihi', date.today())))
                    except Exception:
                        e_tarih_def = date.today()
                    e_tarih = st.date_input('Ödeme Tarihi', value=e_tarih_def, key=prefix+'_e_tarih')
                with e4:
                    e_not = st.text_input('Not', value=edit_row.get('notlar',''), key=prefix+'_e_not')
                btn1, btn2, _ = st.columns([1,1,4])
                with btn1:
                    if st.button('✅ Kaydet', key=prefix+'_e_save', type='primary'):
                        ok = prim_gecmis_guncelle(st.session_state[edit_key], e_donem, e_prim, e_tarih, e_not)
                        if ok:
                            st.session_state[edit_key] = None
                            st.rerun()
                with btn2:
                    if st.button('❌ İptal', key=prefix+'_e_cancel'):
                        st.session_state[edit_key] = None
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.session_state[edit_key] = None
    else:
        st.markdown('<div style="color:#475569;font-size:13px;padding:12px 0">Henüz kayıtlı ödeme yok.</div>', unsafe_allow_html=True)
# ─── PRİM: GÖKHAN YAVUZ
def _prim_gokhan():
    st.markdown('<div class="prim-card">', unsafe_allow_html=True)
    st.markdown('<div style="color:#FCD34D;font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:4px">PRİM HESAPLAMA — GÖKHAN YAVUZ</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#475569;font-size:11px;margin-bottom:16px">Prim = Baz Hakediş (1,5 Maaş) + Ciro Ağırlıklı Bonus &nbsp;·&nbsp; NZXT/AGI hariç</div>', unsafe_allow_html=True)

    # ─ Temel parametreler
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        donem = st.text_input('Dönem', value='Q1 2026', key='gy_donem', placeholder='Örn: Q1 2026')
    with p2:
        aylik_maas = st.number_input('Aylık Maaş (TL)', min_value=0.0, value=115000.0, step=1000.0, format='%.0f', key='gy_maas')
    with p3:
        baz_kat = st.number_input('Baz Katı', min_value=0.0, value=1.5, step=0.1, format='%.1f', key='gy_baz_kat')
    with p4:
        usd_kur = st.number_input('USD/TL Kuru', min_value=1.0, value=38.0, step=0.5, format='%.2f', key='gy_usd_kur')

    st.markdown('<div style="height:2px"></div>', unsafe_allow_html=True)

    # ─ Ciro ve hedef girisi
    g1, g2, g3, g4, g5, g6 = st.columns(6)
    with g1:
        st.markdown('<div class="hm-label" style="color:#A5B4FC">KASA</div>', unsafe_allow_html=True)
    with g2:
        kasa_hedef_pct = st.number_input('KASA Hedef (%)', min_value=0.0, value=30.0, step=0.1, format='%.1f', key='gy_kasa_hedef')
    with g3:
        kasa_gercek_pct = st.number_input('KASA Gerç. (%)', min_value=0.0, value=0.0, step=0.1, format='%.1f', key='gy_kasa_gercek')
    with g4:
        kasa_ciro_usd = st.number_input('KASA Ciro ($)', min_value=0.0, value=0.0, step=100.0, format='%.0f', key='gy_kasa_ciro')
    with g5:
        st.markdown('<div class="hm-label" style="color:#6EE7B7;margin-top:26px">SOĞ</div>', unsafe_allow_html=True)
    with g6:
        pass

    g7, g8, g9, g10, g11, g12 = st.columns(6)
    with g7:
        pass
    with g8:
        sog_hedef_pct = st.number_input('SOĞ Hedef (%)', min_value=0.0, value=35.0, step=0.1, format='%.1f', key='gy_sog_hedef')
    with g9:
        sog_gercek_pct = st.number_input('SOĞ Gerç. (%)', min_value=0.0, value=0.0, step=0.1, format='%.1f', key='gy_sog_gercek')
    with g10:
        sog_ciro_usd = st.number_input('SOĞ Ciro ($)', min_value=0.0, value=0.0, step=100.0, format='%.0f', key='gy_sog_ciro')
    with g11:
        pass
    with g12:
        pass

    # ─ Hesaplama
    kasa_ciro_tl = kasa_ciro_usd * usd_kur
    sog_ciro_tl  = sog_ciro_usd  * usd_kur
    toplam_ciro_usd = kasa_ciro_usd + sog_ciro_usd
    toplam_ciro_tl  = toplam_ciro_usd * usd_kur

    baz_hakdis = baz_kat * aylik_maas

    kasa_carpan = (kasa_gercek_pct / kasa_hedef_pct) if kasa_hedef_pct > 0 else 0.0
    sog_carpan  = (sog_gercek_pct  / sog_hedef_pct)  if sog_hedef_pct  > 0 else 0.0

    toplam_hedef_pct = kasa_hedef_pct + sog_hedef_pct
    kasa_pay = (kasa_hedef_pct / toplam_hedef_pct) if toplam_hedef_pct > 0 else 0.5
    sog_pay  = (sog_hedef_pct  / toplam_hedef_pct) if toplam_hedef_pct > 0 else 0.5

    kasa_fazla = max(0.0, (kasa_carpan - 1.0)) * kasa_pay
    sog_fazla  = max(0.0, (sog_carpan  - 1.0)) * sog_pay
    ciro_bonus = (kasa_fazla + sog_fazla) * baz_hakdis
    toplam_prim = baz_hakdis + ciro_bonus

    kasa_ciro_pay_pct = (kasa_ciro_tl / toplam_ciro_tl * 100) if toplam_ciro_tl > 0 else 0.0
    sog_ciro_pay_pct  = (sog_ciro_tl  / toplam_ciro_tl * 100) if toplam_ciro_tl > 0 else 0.0

    # ─ Sonuç kutusu — derli toplu 9 metrik tek blokta
    st.markdown('<div class="prim-result">', unsafe_allow_html=True)
    st.markdown('<div style="color:#6EE7B7;font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:16px">HESAPLAMA SONUCU</div>', unsafe_allow_html=True)

    r1,r2,r3,r4,r5,r6,r7,r8,r9 = st.columns(9)
    mets = [
        (r1, 'Baz Hakediş', _fmt_tl(baz_hakdis), '#A5B4FC'),
        (r2, 'KASA Hedef', '%{:.1f}'.format(kasa_hedef_pct), '#94A3B8'),
        (r3, 'KASA Gerç.', '%{:.1f}'.format(kasa_gercek_pct), '#A5B4FC'),
        (r4, 'KASA Çarpan', '{:.2f}x'.format(kasa_carpan), '#FCD34D'),
        (r5, 'SOĞ Hedef', '%{:.1f}'.format(sog_hedef_pct), '#94A3B8'),
        (r6, 'SOĞ Gerç.', '%{:.1f}'.format(sog_gercek_pct), '#6EE7B7'),
        (r7, 'SOĞ Çarpan', '{:.2f}x'.format(sog_carpan), '#6EE7B7'),
        (r8, 'Ciro Ağ. Bonus', _fmt_tl(ciro_bonus), '#F59E0B'),
        (r9, 'TOPLAM PRİM', _fmt_tl(toplam_prim), '#10B981'),
    ]
    for col, lbl, val, renk in mets:
        font = '22' if lbl == 'TOPLAM PRİM' else '14'
        weight = '800' if lbl == 'TOPLAM PRİM' else '700'
        with col:
            st.markdown('<div class="hm-label">' + lbl + '</div><div style="font-size:' + font + 'px;font-weight:' + weight + ';color:' + renk + ';font-family:JetBrains Mono,monospace;line-height:1.2">' + val + '</div>', unsafe_allow_html=True)

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

    # 2. satır: ciro detayi
    d1,d2,d3,d4,d5 = st.columns(5)
    with d1: st.markdown('<div class="hm-label">Toplam Ciro</div><div class="hm-val-xs" style="color:#CBD5E1">' + _fmt_usd(toplam_ciro_usd) + ' ≈ ' + _fmt_tl(toplam_ciro_tl) + '</div>', unsafe_allow_html=True)
    with d2: st.markdown('<div class="hm-label">KASA Ciro</div><div class="hm-val-xs" style="color:#A5B4FC">' + _fmt_usd(kasa_ciro_usd) + '</div>', unsafe_allow_html=True)
    with d3: st.markdown('<div class="hm-label">KASA Ciro Payı</div><div class="hm-val-xs" style="color:#A5B4FC">%{:.1f}</div>'.format(kasa_ciro_pay_pct), unsafe_allow_html=True)
    with d4: st.markdown('<div class="hm-label">SOĞ Ciro</div><div class="hm-val-xs" style="color:#6EE7B7">' + _fmt_usd(sog_ciro_usd) + '</div>', unsafe_allow_html=True)
    with d5: st.markdown('<div class="hm-label">SOĞ Ciro Payı</div><div class="hm-val-xs" style="color:#6EE7B7">%{:.1f}</div>'.format(sog_ciro_pay_pct), unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ─ Kaydet
    st.markdown('<div class="prim-card">', unsafe_allow_html=True)
    st.markdown('<div style="color:#94A3B8;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px">PRİM ÖDEMESİ KAYDET</div>', unsafe_allow_html=True)
    op1,op2,op3 = st.columns([1.5,1,2])
    with op1:
        odeme_tarihi_gy = st.date_input('Ödeme Tarihi', value=date.today(), key='gy_odeme_tarihi')
    with op2:
        odeme_not_gy = st.text_input('Not (opsiyonel)', placeholder='Örn: Q1 ödemesi', key='gy_odeme_not')
    with op3:
        st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
        if st.button('💾 Kaydet', key='gy_kaydet', type='primary'):
            if toplam_prim > 0 and donem:
                ok = prim_gecmis_kaydet('gokhan_yavuz', donem, toplam_prim, odeme_tarihi_gy, odeme_not_gy)
                if ok:
                    st.success('✅ ' + donem + ' dönemi ' + _fmt_tl(toplam_prim) + ' prim ödemesi kaydedildi.')
                    st.rerun()
                else:
                    st.error('Kayıt sırasında hata oluştu.')
            else:
                st.warning('Dönem adı ve prim tutarı girilmeli.')
    st.markdown('</div>', unsafe_allow_html=True)

    # ─ Geçmiş
    st.markdown('<div class="prim-card">', unsafe_allow_html=True)
    st.markdown('<div style="color:#94A3B8;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px">GEÇMİŞ PRİM ÖDEMELERİ — GÖKHAN YAVUZ</div>', unsafe_allow_html=True)
    _gecmis_odemeler('gokhan_yavuz', 'gy')
    st.markdown('</div>', unsafe_allow_html=True)
# ─── PRİM: AYHAN EROĞLU
def _prim_ayhan():
    st.markdown('<div class="prim-card">', unsafe_allow_html=True)
    st.markdown('<div style="color:#FCD34D;font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:4px">PRİM HESAPLAMA — AYHAN EROĞLU</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#475569;font-size:11px;margin-bottom:16px">Prim = Satılan adet × adet başı USD prim × USD/TL kuru</div>', unsafe_allow_html=True)

    # Birim primler + kur
    b1,b2,b3,b4,b5 = st.columns(5)
    with b1: mon_birim  = st.number_input('Monitör ($/adet)', min_value=0.0, value=0.50, step=0.01, format='%.2f', key='ay_mon_birim')
    with b2: kasa_birim = st.number_input('Kasa ($/adet)', min_value=0.0, value=0.50, step=0.01, format='%.2f', key='ay_kasa_birim')
    with b3: ekart_birim= st.number_input('Ekran Kartı ($/adet)', min_value=0.0, value=1.00, step=0.01, format='%.2f', key='ay_ekart_birim')
    with b4: ssd_birim  = st.number_input('SSD&RAM ($/adet)', min_value=0.0, value=0.50, step=0.01, format='%.2f', key='ay_ssd_birim')
    with b5: usd_kur    = st.number_input('USD/TL Kuru', min_value=1.0, value=38.0, step=0.5, format='%.2f', key='ay_usd_kur')

    # Adet girisi
    a1,a2,a3,a4,a5 = st.columns(5)
    with a1: ay_donem   = st.text_input('Dönem', value='Q1 2026', key='ay_donem', placeholder='Örn: Q1 2026')
    with a2: mon_adet   = st.number_input('Monitör Adet', min_value=0, value=0, step=1, key='ay_mon_adet')
    with a3: kasa_adet  = st.number_input('Kasa Adet', min_value=0, value=0, step=1, key='ay_kasa_adet')
    with a4: ekart_adet = st.number_input('Ekran Kartı Adet', min_value=0, value=0, step=1, key='ay_ekart_adet')
    with a5: ssd_adet   = st.number_input('SSD&RAM Adet', min_value=0, value=0, step=1, key='ay_ssd_adet')

    mon_usd   = mon_adet   * mon_birim
    kasa_usd  = kasa_adet  * kasa_birim
    ekart_usd = ekart_adet * ekart_birim
    ssd_usd   = ssd_adet   * ssd_birim
    toplam_usd = mon_usd + kasa_usd + ekart_usd + ssd_usd
    toplam_tl  = toplam_usd * usd_kur

    # Sonuç kutusu
    st.markdown('<div class="prim-result">', unsafe_allow_html=True)
    st.markdown('<div style="color:#6EE7B7;font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:16px">HESAPLAMA SONUCU</div>', unsafe_allow_html=True)

    r1,r2,r3,r4,r5,r6,r7 = st.columns(7)
    mets = [
        (r1, 'Monitör Prim', '${:.2f}'.format(mon_usd), '#CBD5E1'),
        (r2, 'Kasa Prim', '${:.2f}'.format(kasa_usd), '#CBD5E1'),
        (r3, 'E.Kartı Prim', '${:.2f}'.format(ekart_usd), '#CBD5E1'),
        (r4, 'SSD&RAM Prim', '${:.2f}'.format(ssd_usd), '#CBD5E1'),
        (r5, 'Toplam Adet', '{:,d}'.format(mon_adet+kasa_adet+ekart_adet+ssd_adet), '#94A3B8'),
        (r6, 'TOPLAM ($)', '${:,.2f}'.format(toplam_usd), '#FCD34D'),
        (r7, 'TOPLAM (TL)', _fmt_tl(toplam_tl), '#10B981'),
    ]
    for col, lbl, val, renk in mets:
        font = '22' if 'TOPLAM (TL)' in lbl else '14'
        weight = '800' if 'TOPLAM (TL)' in lbl else '700'
        with col:
            st.markdown('<div class="hm-label">' + lbl + '</div><div style="font-size:' + font + 'px;font-weight:' + weight + ';color:' + renk + ';font-family:JetBrains Mono,monospace;line-height:1.2">' + val + '</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Kaydet
    st.markdown('<div class="prim-card">', unsafe_allow_html=True)
    st.markdown('<div style="color:#94A3B8;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px">PRİM ÖDEMESİ KAYDET</div>', unsafe_allow_html=True)
    op1,op2,op3 = st.columns([1.5,1,2])
    with op1:
        odeme_tarihi_ay = st.date_input('Ödeme Tarihi', value=date.today(), key='ay_odeme_tarihi')
    with op2:
        odeme_not_ay = st.text_input('Not (opsiyonel)', placeholder='Örn: Q1 ödemesi', key='ay_odeme_not')
    with op3:
        st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
        if st.button('💾 Kaydet', key='ay_kaydet', type='primary'):
            if toplam_tl > 0 and ay_donem:
                ok = prim_gecmis_kaydet('ayhan_eroglu', ay_donem, toplam_tl, odeme_tarihi_ay, odeme_not_ay)
                if ok:
                    st.success('✅ ' + ay_donem + ' dönemi ' + _fmt_tl(toplam_tl) + ' prim ödemesi kaydedildi.')
                    st.rerun()
                else:
                    st.error('Kayıt sırasında hata oluştu.')
            else:
                st.warning('Dönem adı ve prim tutarı girilmeli.')
    st.markdown('</div>', unsafe_allow_html=True)

    # Geçmiş
    st.markdown('<div class="prim-card">', unsafe_allow_html=True)
    st.markdown('<div style="color:#94A3B8;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px">GEÇMİŞ PRİM ÖDEMELERİ — AYHAN EROĞLU</div>', unsafe_allow_html=True)
    _gecmis_odemeler('ayhan_eroglu', 'ay')
    st.markdown('</div>', unsafe_allow_html=True)
# ─── SEKME 1: ÜRÜN KARLILIK
def _urun_karlilik():
    st.markdown('<div class="hm-card">', unsafe_allow_html=True)
    st.markdown('<div style="color:#A5B4FC;font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:16px">ÜRÜN KARLILIK HESAPLAYICI</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#FFFFFF;font-size:14px;font-weight:700;margin-bottom:14px">Hızlı Hesap</div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1.5,1,1])
    with c1: urun_adi = st.text_input('Ürün Adı (opsiyonel)', placeholder='Örn: Monitor XG27', key='uk_ad')
    with c2: alis = st.number_input('Alış Fiyatı ($)', min_value=0.0, value=0.0, step=0.01, format='%.2f', key='uk_alis')
    with c3: masraf_tipi = st.selectbox('Ek Masraf Tipi', ['%','$'], key='uk_masraf_tipi')
    c4,c5,c6 = st.columns([1.5,1,1])
    with c4:
        masraf_label = 'Ek Masraf (%)' if masraf_tipi == '%' else 'Ek Masraf ($)'
        masraf_deger = st.number_input(masraf_label, min_value=0.0, value=0.0, step=(0.1 if masraf_tipi=='%' else 0.01), format=('%.1f' if masraf_tipi=='%' else '%.2f'), key='uk_masraf')
    with c5: satis = st.number_input('Satış Fiyatı ($)', min_value=0.0, value=0.0, step=0.01, format='%.2f', key='uk_satis')
    with c6: indirim = st.number_input('İndirim ($)', min_value=0.0, value=0.0, step=0.01, format='%.2f', key='uk_indirim')
    if alis > 0 and satis > 0:
        maliyet = _toplam_maliyet(alis, masraf_tipi, masraf_deger)
        kar_norm = _kar(maliyet, satis)
        marj_norm = _marj(maliyet, satis)
        renk = _renk(kar_norm)
        ind_satis = satis - indirim if indirim > 0 else None
        if ind_satis is not None and ind_satis > 0:
            kar_ind = _kar(maliyet, ind_satis)
            renk_ind = _renk(kar_ind)
        st.markdown('<div class="hm-result-box">', unsafe_allow_html=True)
        st.markdown('<div style="color:#94A3B8;font-size:11px;font-weight:600;margin-bottom:12px">' + (urun_adi+' — ' if urun_adi else '') + 'Toplam Maliyet: ' + _fmt(maliyet) + '</div>', unsafe_allow_html=True)
        if ind_satis and ind_satis > 0:
            r1,r2,r3,r4,r5 = st.columns(5)
            cols = [r1,r2,r3,r4,r5]
            labels = ['Satış Fiyatı','Kar ($)','Marj (%)','İnd. Fiyat','İnd. Kar ($)']
            vals = [('<div class="hm-val">$'+'{:,.2f}'.format(satis)+'</div>'),('<div class="hm-val" style="color:'+renk+'">$'+'{:,.2f}'.format(kar_norm)+'</div>'),('<div class="hm-val" style="color:'+renk+'">%'+'{:.1f}'.format(marj_norm)+'</div>'),('<div class="hm-val-sm" style="color:#F59E0B">$'+'{:,.2f}'.format(ind_satis)+'</div>'),('<div class="hm-val-sm" style="color:'+renk_ind+'">$'+'{:,.2f}'.format(kar_ind)+'</div>')]
        else:
            r1,r2,r3 = st.columns(3)
            cols = [r1,r2,r3]
            labels = ['Satış Fiyatı','Kar ($)','Marj (%)']
            vals = [('<div class="hm-val">$'+'{:,.2f}'.format(satis)+'</div>'),('<div class="hm-val" style="color:'+renk+'">$'+'{:,.2f}'.format(kar_norm)+'</div>'),('<div class="hm-val" style="color:'+renk+'">%'+'{:.1f}'.format(marj_norm)+'</div>')]
        for col,lbl,val in zip(cols,labels,vals):
            with col: st.markdown('<div class="hm-label">'+lbl+'</div>'+val, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="color:#475569;font-size:13px;padding:16px 0">Alış ve satış fiyatını girerek sonucu görün.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="hm-sep"></div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#FFFFFF;font-size:14px;font-weight:700;margin-bottom:6px">Toplu Karşılaştırma</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#64748B;font-size:12px;margin-bottom:14px">Birden fazla ürünü yan yana ekleyip karşılaştır.</div>', unsafe_allow_html=True)
    if 'uk_liste' not in st.session_state: st.session_state.uk_liste = []
    if 'uk_sayac' not in st.session_state: st.session_state.uk_sayac = 0
    with st.expander('+ Ürün Ekle', expanded=(len(st.session_state.uk_liste)==0)):
        fa1,fa2,fa3 = st.columns([2,1,1])
        with fa1: fa_ad = st.text_input('Ürün Adı', placeholder='Ürün adı veya kodu', key='fa_ad')
        with fa2: fa_alis = st.number_input('Alış ($)', min_value=0.0, value=0.0, step=0.01, format='%.2f', key='fa_alis')
        with fa3: fa_masraf_tipi = st.selectbox('Masraf Tipi', ['%','$'], key='fa_masraf_tipi')
        fb1,fb2,fb3 = st.columns([2,1,1])
        with fb1:
            fa_masraf_label = 'Ek Masraf (%)' if fa_masraf_tipi=='%' else 'Ek Masraf ($)'
            fa_masraf = st.number_input(fa_masraf_label, min_value=0.0, value=0.0, step=(0.1 if fa_masraf_tipi=='%' else 0.01), format=('%.1f' if fa_masraf_tipi=='%' else '%.2f'), key='fa_masraf')
        with fb2: fa_satis = st.number_input('Satış ($)', min_value=0.0, value=0.0, step=0.01, format='%.2f', key='fa_satis')
        with fb3: fa_indirim = st.number_input('İndirim ($)', min_value=0.0, value=0.0, step=0.01, format='%.2f', key='fa_indirim')
        if st.button('Listeye Ekle', key='fa_ekle', type='primary'):
            if fa_alis > 0 and fa_satis > 0:
                st.session_state.uk_sayac += 1
                me = _toplam_maliyet(fa_alis, fa_masraf_tipi, fa_masraf)
                ke = _kar(me, fa_satis)
                mre = _marj(me, fa_satis)
                is2 = fa_satis - fa_indirim if fa_indirim > 0 else None
                kie = _kar(me, is2) if is2 and is2 > 0 else None
                mie = _marj(me, is2) if is2 and is2 > 0 else None
                st.session_state.uk_liste.append({'id':st.session_state.uk_sayac,'ad':fa_ad or ('Ürün '+str(st.session_state.uk_sayac)),'alis':fa_alis,'masraf_tipi':fa_masraf_tipi,'masraf':fa_masraf,'maliyet':me,'satis':fa_satis,'indirim':fa_indirim,'kar':ke,'marj':mre,'ind_satis':is2,'kar_ind':kie,'marj_ind':mie})
                st.rerun()
            else: st.warning('Alış ve satış fiyatı girilmeli.')
    if st.session_state.uk_liste:
        h1,h2,h3,h4,h5,h6,h7,h8 = st.columns([2,1.2,1.2,1.2,1.2,1.2,1.2,0.6])
        for col,bas in zip([h1,h2,h3,h4,h5,h6,h7,h8],['Ürün','Alış ($)','Maliyet ($)','Satış ($)','Kar ($)','Marj (%)','İnd. Kar ($)','']):
            with col: st.markdown('<div class="hm-label">'+bas+'</div>', unsafe_allow_html=True)
        silinecek = None
        for u in st.session_state.uk_liste:
            ru = _renk(u['kar'])
            u1,u2,u3,u4,u5,u6,u7,u8 = st.columns([2,1.2,1.2,1.2,1.2,1.2,1.2,0.6])
            with u1: st.markdown('<div style="color:#E2E8F0;font-size:13px;padding:8px 0">'+u['ad']+'</div>', unsafe_allow_html=True)
            with u2: st.markdown('<div style="color:#CBD5E1;font-size:13px;padding:8px 0">$'+'{:,.2f}'.format(u['alis'])+'</div>', unsafe_allow_html=True)
            with u3: st.markdown('<div style="color:#94A3B8;font-size:13px;padding:8px 0">$'+'{:,.2f}'.format(u['maliyet'])+'</div>', unsafe_allow_html=True)
            with u4: st.markdown('<div style="color:#CBD5E1;font-size:13px;padding:8px 0">$'+'{:,.2f}'.format(u['satis'])+'</div>', unsafe_allow_html=True)
            with u5: st.markdown('<div style="color:'+ru+';font-size:13px;font-weight:700;padding:8px 0">$'+'{:,.2f}'.format(u['kar'])+'</div>', unsafe_allow_html=True)
            with u6: st.markdown('<div style="color:'+ru+';font-size:13px;font-weight:700;padding:8px 0">%'+'{:.1f}'.format(u['marj'])+'</div>', unsafe_allow_html=True)
            with u7:
                if u['kar_ind'] is not None:
                    ri = _renk(u['kar_ind'])
                    st.markdown('<div style="color:'+ri+';font-size:13px;padding:8px 0">$'+'{:,.2f}'.format(u['kar_ind'])+'</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="color:#475569;font-size:12px;padding:8px 0">—</div>', unsafe_allow_html=True)
            with u8:
                if st.button('✕', key='uk_sil_'+str(u['id']), help='Sil'): silinecek = u['id']
            st.markdown('<div style="height:1px;background:rgba(255,255,255,0.04)"></div>', unsafe_allow_html=True)
        if silinecek:
            st.session_state.uk_liste = [x for x in st.session_state.uk_liste if x['id'] != silinecek]
            st.rerun()
        if st.button('Listeyi Temizle', key='uk_temizle'):
            st.session_state.uk_liste = []
            st.rerun()
    else:
        st.markdown('<div style="color:#475569;font-size:13px;padding:12px 0">Henüz ürün eklenmedi.</div>', unsafe_allow_html=True)

# ─── SEKME 2: BREAK-EVEN
def _breakeven():
    st.markdown('<div class="hm-card">', unsafe_allow_html=True)
    st.markdown('<div style="color:#FCD34D;font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:16px">KIRILMA NOKTASI HESAPLAYICI</div>', unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1:
        st.markdown('<div style="color:#FFFFFF;font-size:14px;font-weight:700;margin-bottom:14px">Parametreler</div>', unsafe_allow_html=True)
        periyot = st.selectbox('Periyot', ['Günlük','Haftalık','Aylık','Yıllık'], index=2, key='be_periyot')
        gider = st.number_input('Sabit Gider ($) — '+periyot, min_value=0.0, value=0.0, step=10.0, format='%.2f', key='be_gider')
        marj = st.number_input('Ortalama Marj (%)', min_value=0.1, max_value=99.9, value=30.0, step=0.1, format='%.1f', key='be_marj')
        ort_fiyat = st.number_input('Ortalama Ürün Fiyatı ($)', min_value=0.0, value=0.0, step=1.0, format='%.2f', key='be_ort_fiyat')
        mevcut = st.number_input('Mevcut Ciro ($) — '+periyot, min_value=0.0, value=0.0, step=100.0, format='%.2f', key='be_mevcut')
    with c2:
        st.markdown('<div style="color:#FFFFFF;font-size:14px;font-weight:700;margin-bottom:14px">Sonuç</div>', unsafe_allow_html=True)
        if gider > 0 and marj > 0:
            hedef = gider / (marj / 100)
            kalan_ciro = max(0.0, hedef - mevcut)
            ilerleme = min(1.0, mevcut / hedef) if hedef > 0 else 0.0
            asindi = mevcut >= hedef
            st.markdown('<div class="hm-label">Hedef Ciro ('+periyot+')</div><div class="hm-val" style="color:#A5B4FC">$'+'{:,.0f}'.format(hedef)+'</div>', unsafe_allow_html=True)
            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
            pct = ilerleme * 100
            bar_renk = '#10B981' if asindi else '#6366F1'
            st.markdown('<div class="hm-label">İlerleme</div><div style="margin:6px 0 4px;height:10px;background:rgba(255,255,255,0.08);border-radius:5px;overflow:hidden"><div style="height:100%;width:'+'{:.1f}'.format(pct)+'%;background:'+bar_renk+';border-radius:5px"></div></div><div style="color:#94A3B8;font-size:11px;text-align:right">%'+'{:.1f}'.format(pct)+' tamamlandı</div>', unsafe_allow_html=True)
            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
            if asindi:
                fazla = mevcut - hedef
                st.markdown('<div class="hm-label">Durum</div><div class="hm-val-sm" style="color:#10B981">Hedef Aşıldı</div><div style="color:#6EE7B7;font-size:12px;margin-top:4px">+$'+'{:,.0f}'.format(fazla)+' fazla</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="hm-label">Kalan Ciro</div><div class="hm-val-sm" style="color:#F59E0B">$'+'{:,.0f}'.format(kalan_ciro)+'</div>', unsafe_allow_html=True)
            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
            if ort_fiyat > 0:
                hedef_adet = hedef / ort_fiyat
                kalan_adet = kalan_ciro / ort_fiyat
                st.markdown('<div class="hm-label">Hedef Adet / Kalan</div><div class="hm-val-sm" style="color:#C4B5FD">'+'{:,.0f}'.format(hedef_adet)+' adet</div><div style="color:#94A3B8;font-size:12px;margin-top:2px">Kalan: '+'{:,.0f}'.format(kalan_adet)+' adet</div>', unsafe_allow_html=True)
                st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
            gun_map = {'Günlük':1,'Haftalık':7,'Aylık':30,'Yıllık':365}
            gun_sayisi = gun_map.get(periyot, 30)
            if kalan_ciro > 0:
                gunluk_ciro = kalan_ciro / gun_sayisi
                st.markdown('<div class="hm-label">Hedefe Ulaşmak İçin</div><div class="hm-val-sm" style="color:#FCD34D">$'+'{:,.0f}'.format(gunluk_ciro)+'/gün</div><div style="color:#94A3B8;font-size:11px;margin-top:2px">'+('{:,.0f}'.format(kalan_ciro/ort_fiyat/gun_sayisi)+' adet/gün' if ort_fiyat > 0 else '')+'</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#475569;font-size:13px;padding:20px 0">Gider ve marj girerek kırılma noktasını hesaplayın.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ─── ANA RUN
def run():
    st.markdown(_css(), unsafe_allow_html=True)
    st.markdown('<div style="margin-bottom:24px"><div style="display:inline-block;padding:5px 14px;background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.3);border-radius:20px;margin-bottom:12px"><span style="color:#FCD34D;font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase">Hesap Makinesi</span></div><h1 style="font-family:Inter,sans-serif;font-size:clamp(20px,4vw,32px);font-weight:800;color:#FFFFFF;margin:0;line-height:1.1">Hesap Makinesi</h1><p style="color:#64748B;font-size:13px;margin-top:6px">Ürün karlılık analizi, kırılma noktası ve prim hesaplama</p></div>', unsafe_allow_html=True)
    if 'hm_sekme' not in st.session_state: st.session_state.hm_sekme = 'karlilik'
    t1,t2,t3,t4,_ = st.columns([1.5,1.5,1.5,1.5,3])
    with t1:
        if st.button('Ürün Karlılık', key='tab_karlilik', type=('primary' if st.session_state.hm_sekme=='karlilik' else 'secondary'), use_container_width=True):
            st.session_state.hm_sekme='karlilik'; st.rerun()
    with t2:
        if st.button('Kırılma Noktası', key='tab_breakeven', type=('primary' if st.session_state.hm_sekme=='breakeven' else 'secondary'), use_container_width=True):
            st.session_state.hm_sekme='breakeven'; st.rerun()
    with t3:
        if st.button('💰 Gökhan Prim', key='tab_prim_gy', type=('primary' if st.session_state.hm_sekme=='prim_gokhan' else 'secondary'), use_container_width=True):
            st.session_state.hm_sekme='prim_gokhan'; st.rerun()
    with t4:
        if st.button('💰 Ayhan Prim', key='tab_prim_ay', type=('primary' if st.session_state.hm_sekme=='prim_ayhan' else 'secondary'), use_container_width=True):
            st.session_state.hm_sekme='prim_ayhan'; st.rerun()
    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
    if st.session_state.hm_sekme == 'karlilik': _urun_karlilik()
    elif st.session_state.hm_sekme == 'breakeven': _breakeven()
    elif st.session_state.hm_sekme == 'prim_gokhan': _prim_gokhan()
    elif st.session_state.hm_sekme == 'prim_ayhan': _prim_ayhan()
