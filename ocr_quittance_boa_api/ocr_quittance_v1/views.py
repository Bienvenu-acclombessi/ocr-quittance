# myapp/views.py

import json
import re
from django.conf import settings
import fitz  # PyMuPDF
from PIL import Image,ImageOps
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from .serializers import PDFUploadSerializer
import google.generativeai as genai
from django.core.files.uploadedfile import InMemoryUploadedFile
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from google.api_core.exceptions import ResourceExhausted  # Assurez-vous d'avoir installé le package google-api-core
import random


genai.configure(api_key=settings.GOOGLE_GENAI_API_KEY)
class ProcessPDFView(APIView):
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'file': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY, description='PDF file to process'),
            },
            required=['file'],
        ),
        responses={
            200: openapi.Response(
                description='File processed successfully',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'amount': openapi.Schema(type=openapi.TYPE_STRING, description='Amount'),
                                'student_name': openapi.Schema(type=openapi.TYPE_STRING, description='Student name'),
                                'stamp_fees': openapi.Schema(type=openapi.TYPE_STRING, description='Stamp fees'),
                                'currency': openapi.Schema(type=openapi.TYPE_STRING, description='Currency'),
                                'date': openapi.Schema(type=openapi.TYPE_STRING, description='Date'),
                                'reference': openapi.Schema(type=openapi.TYPE_STRING, description='Reference'),
                                'payment_reason': openapi.Schema(type=openapi.TYPE_STRING, description='Payment reason'),
                            },
                        ),
                    },
                ),
            ),
            400: openapi.Response(
                description='Bad Request',
                examples={
                    'application/json': {
                        'file': ['This field is required.'],
                    }
                }
            ),
            500: openapi.Response(
                description='Internal Server Error',
                examples={
                    'application/json': {
                        'error': 'Failed to parse response from model',
                    }
                }
            ),
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = PDFUploadSerializer(data=request.data)
        
        if serializer.is_valid():
            uploaded_file = serializer.validated_data['file']
            
            # verfification
            # Vérifiez le type de fichier
            if isinstance(uploaded_file, InMemoryUploadedFile):
                if uploaded_file.content_type == 'application/pdf':
                    # Traitez le fichier PDF
                    pdf_file = uploaded_file
                    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
                    images = []
                    for page_num in range(len(doc)):
                        page = doc.load_page(page_num)
                        pix = page.get_pixmap()
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        images.append(img)

                    # Supposons que nous traitons uniquement la première page pour cet exemple
                    img_path = 'page.png'
                    images[0].save(img_path)
                    img=Image.open('page.png')
                elif uploaded_file.content_type.startswith('image/'):
                    # Traitez le fichier image
                    img = Image.open(uploaded_file)
                else:
                    return Response({"error": "Unsupported file type"}, status=status.HTTP_400_BAD_REQUEST)

            # Supposons que nous traitons uniquement la première page pour cet exemple
            
            model = genai.GenerativeModel('gemini-1.5-flash')
            
           
            prompt="""Veuillez analyser l'image de la quittance jointe et extraire les informations suivantes :
                        1. Amount : Le montant majoré( precède la phrase 'majore de') de l'opération, excluant les frais de timbre.Il faut le  convertir en réel pour l'utilisation facile, c'est à dire sans , ou . .
                        2. Student Name : Le nom de l'étudiant associé à la quittance.
                        3. Stamp Fees : Les frais de timbre inclus dans la quittance. Ils sont toujours situés après le montant et ne peuvent jamais être égaux au montant. Laissez ce champ vide si les frais de timbre ne sont pas mentionnés.
                        4. Currency : La devise dans laquelle le montant de la quittance est spécifié.
                        5. Date : La date mentionnée sur la quittance.
                        6. Reference : Le numéro de référence sur la quittance.
                        7. Payment Reason : Le motif du paiement mentionné sur la quittance (situé après ou en dessous du nom de l'étudiant ou après un slash (/)).
                        8. Account Number : Le numéro du compte qui a été crédité.

                        Retournez les informations extraites au format JSON pur sans aucun formatage ou commentaire supplémentaire. Assurez-vous que la sortie soit un JSON valide pour éviter toute erreur de parsing json.

                        Si les informations ne peuvent pas être trouvées dans l'image, veuillez retourner le JSON avec des attributs vides comme indiqué ci-dessous :
                        {
                            "amount": "",
                            "student_name": "",
                            "stamp_fees": "",
                            "currency": "",
                            "date": "",
                            "reference": "",
                            "payment_reason": ""
                            "account_number": ""
                        }
                        """
            response = {}
            
            
            has_resource_exhausted_error = True
            
    
    
            i=1
            while has_resource_exhausted_error:
                i=i+1
                try:
                    has_resource_exhausted_error = False
                    response = model.generate_content([prompt, img])
                
                except ResourceExhausted as e:
                    genai.configure(api_key=random.choice(settings.GOOGLE_GENAI_API_KEYS))
                    has_resource_exhausted_error = True
                    if i==30: raise e
                    
                             


            try:
                cleaned_response = re.sub(r'```json|```', '', response.text).strip()
                extracted_data = json.loads(cleaned_response)
                response_json = {
                    "amount": extracted_data.get("amount", ""),
                    "student_name": extracted_data.get("student_name", ""),
                    "stamp_fees": extracted_data.get("stamp_fees", ""),
                    "currency": extracted_data.get("currency", ""),
                    "date": extracted_data.get("date", ""),
                    "reference": extracted_data.get("reference", ""),
                    "payment_reason": extracted_data.get("payment_reason", ""),
                    "account_number": extracted_data.get("account_number", "")
                }
            except json.JSONDecodeError:
                return Response({"error": "Failed to parse response from model"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
            return Response({"data":response_json}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
