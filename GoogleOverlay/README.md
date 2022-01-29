# Google Maps Overlay Deployment - JavaScript 

This web application is used to view sidewalk layer on Google maps.
The app is created using TypeScript and served using Webpack module bundler.

## Setup

To deploy the application replace GOOGLE_API_KEY in typescript (*.ts) files inside 'src' folder with your Google API keys.
The required npm modules can be found in 'package.json' file. Run 'npm install' inside the folder where package.json is present.

The server can then be started using 'npm run watch' in the command line.
(Webpack config run using the above command can be found in webpack.dev.js file.)

The links to access google overlay: 
'IP-address-of-server:8080/eagleview.html'
'IP-address-of-server:8080/'
