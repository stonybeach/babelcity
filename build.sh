#! /bin/bash
echo Installing python dependencies ...
pip install -r requirements.txt

echo Installing npm dependencies ...
cd web
npm install

echo Building in web/dist ...
npm run build
cd ..

echo You are ready! Please start using:
echo   python -m babelcity.main