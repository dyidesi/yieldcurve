# Yield Curve Explorer

Streamlit app for government yield curves: one country over time, countries side by side, which curves are inverted, and the US inversion record against NBER recessions.

US curves use daily Federal Reserve Treasury yields from [FRED](https://fred.stlouisfed.org/). Other countries use the built-in reference values in `streamlit_app.py`.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Live app: [yieldcurvebycountry.streamlit.app](https://yieldcurvebycountry.streamlit.app/)

## Publish at yieldcurve.streamlit.app

The GitHub repo is the source. Streamlit Community Cloud assigns the public URL when the app is deployed, and the subdomain is chosen in that form.

1. Sign in at [share.streamlit.io](https://share.streamlit.io) with the GitHub account that owns this repo.
2. Choose **Create app**.
3. Repository: `dyidesi/yieldcurve`, branch: `main`, main file: `streamlit_app.py`.
4. Set the app URL / subdomain to `yieldcurve`.
5. Deploy. The app is then at [https://yieldcurve.streamlit.app](https://yieldcurve.streamlit.app).

The repo must stay public for the free Community Cloud plan. If `yieldcurve` is already taken, Streamlit will ask for another subdomain.
